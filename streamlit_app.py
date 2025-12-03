import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
from dateutil.relativedelta import relativedelta

# --- Налаштування сторінки ---
st.set_page_config(
    page_title="Кредитний Калькулятор",
    page_icon="💸",
    layout="wide"
)

# --- Логіка розрахунку ---
@st.cache_data
def calculate_schedule(principal, annual_rate, start_date, 
                       years=None, fixed_payment=None, 
                       monthly_extra=0, irregular_payments=None):
    """
    Універсальна функція розрахунку.
    Може працювати у двох режимах:
    1. Фіксований термін (years вказано, fixed_payment=None) -> рахуємо аннуїтет.
    2. Фіксований платіж (years=None, fixed_payment вказано) -> рахуємо термін.
    """
    if irregular_payments is None:
        irregular_payments = {}

    monthly_rate = annual_rate / 12 / 100
    schedule = []
    remaining_balance = principal
    current_date = start_date
    
    # Визначаємо базовий щомісячний платіж
    if fixed_payment is not None:
        # Режим: "За сумою платежу"
        base_payment = fixed_payment
        # Перевірка, чи платіж перекриває хоча б відсотки
        first_month_interest = principal * monthly_rate
        if base_payment <= first_month_interest:
            return pd.DataFrame() # Повертаємо порожній DF як помилку
    else:
        # Режим: "За терміном"
        total_months_planned = years * 12
        if monthly_rate > 0:
            base_payment = principal * (monthly_rate * (1 + monthly_rate)**total_months_planned) / ((1 + monthly_rate)**total_months_planned - 1)
        else:
            base_payment = principal / total_months_planned

    # Ліміт ітерацій (наприклад, 50 років), щоб уникнути нескінченного циклу при малих платежах
    max_months = 600 
    
    for i in range(1, max_months + 1):
        if remaining_balance <= 0.01:
            break

        interest_payment = remaining_balance * monthly_rate
        
        # Основна логіка платежу
        # Базова частина (тіло + відсотки)
        current_base_payment = base_payment
        
        # Додаткові платежі
        extra = monthly_extra
        if i in irregular_payments:
            extra += irregular_payments[i]
            
        # Загальна сума спроби платежу
        total_payment_attempt = current_base_payment + extra
        
        # Якщо залишок менший за платіж -> коригуємо (фінальний місяць)
        if total_payment_attempt >= remaining_balance + interest_payment:
            total_payment = remaining_balance + interest_payment
            principal_payment = remaining_balance
            remaining_balance = 0
            # Реальна "доплата" - це все, що понад нараховані відсотки
            # Але для коректності статистики "Extra" вважаємо те, що більше Base
            # В останньому місяці це складно розділити, тому спростимо:
            extra_paid_in_record = max(0, total_payment - (interest_payment + (base_payment - interest_payment)))
        else:
            total_payment = total_payment_attempt
            # Спочатку гасимо відсотки
            principal_payment = total_payment - interest_payment
            remaining_balance -= principal_payment
            extra_paid_in_record = extra # Записуємо чистий екстра платіж

        schedule.append({
            "Номер місяця": i,
            "Дата": current_date,
            "Загальний платіж": total_payment,
            "Тіло кредиту": principal_payment,
            "Відсотки": interest_payment,
            "Додатково погашено": extra_paid_in_record, # Для відображення
            "Залишок боргу": remaining_balance
        })
        
        current_date += relativedelta(months=1)

    return pd.DataFrame(schedule)

# --- Sidebar ---
st.sidebar.header("⚙️ Параметри кредиту")

# 1. Загальні ввідні
loan_amount = st.sidebar.number_input("Сума кредиту (грн)", min_value=1000, value=500000, step=1000)
interest_rate = st.sidebar.number_input("Річна ставка (%)", min_value=0.1, value=15.0, step=0.1)
start_date = st.sidebar.date_input("Дата початку", value=date.today())

st.sidebar.markdown("---")

# 2. Вибір режиму
calc_mode = st.sidebar.radio(
    "Спосіб розрахунку:",
    ("За терміном (років)", "За сумою платежу")
)

target_years = None
target_payment = None

if calc_mode == "За терміном (років)":
    target_years = st.sidebar.slider("Бажаний термін (років)", 1, 30, 5)
else:
    # Підказка мінімального платежу
    min_payment = (loan_amount * (interest_rate / 100 / 12)) + 1
    target_payment = st.sidebar.number_input(
        f"Фіксований платіж (мін. {min_payment:.2f} грн)", 
        min_value=float(int(min_payment)), 
        value=float(int(min_payment * 1.5)), 
        step=500.0
    )

st.sidebar.markdown("---")
st.sidebar.header("🚀 Дострокове погашення")
st.sidebar.caption("Додаткові платежі *поверх* розрахованого вище графіку.")

monthly_extra_pay = st.sidebar.number_input("Регулярна доплата (грн/міс)", min_value=0, value=0, step=500)

st.sidebar.subheader("Разові погашення")
irregular_data = pd.DataFrame([{"Місяць №": 12, "Сума (грн)": 0}])
edited_df = st.sidebar.data_editor(irregular_data, num_rows="dynamic", hide_index=True)

irregular_payments_dict = {}
if not edited_df.empty:
    for _, row in edited_df.iterrows():
        try:
            m = int(row["Місяць №"])
            val = float(row["Сума (грн)"])
            if m > 0 and val > 0:
                irregular_payments_dict[m] = irregular_payments_dict.get(m, 0) + val
        except:
            pass

# --- Основна частина ---
st.title("📊 Кредитний Аналізатор")

# Перевірка коректності введення для режиму "За сумою"
valid_input = True
if target_payment is not None:
    monthly_rate_check = interest_rate / 12 / 100
    if target_payment <= loan_amount * monthly_rate_check:
        st.error(f"⚠️ Ваш платіж ({target_payment} грн) менший за щомісячні відсотки! Борг ніколи не буде виплачений. Збільшіть суму платежу.")
        valid_input = False

if valid_input:
    # 1. Базовий сценарій (без переплат, чистий графік)
    df_base = calculate_schedule(
        principal=loan_amount, 
        annual_rate=interest_rate, 
        start_date=start_date, 
        years=target_years, 
        fixed_payment=target_payment,
        monthly_extra=0, 
        irregular_payments={}
    )

    # 2. Реальний сценарій (з переплатами)
    df_real = calculate_schedule(
        principal=loan_amount, 
        annual_rate=interest_rate, 
        start_date=start_date, 
        years=target_years, 
        fixed_payment=target_payment,
        monthly_extra=monthly_extra_pay, 
        irregular_payments=irregular_payments_dict
    )

    if df_base.empty or df_real.empty:
        st.error("Помилка розрахунку. Перевірте вхідні дані.")
    else:
        # --- Метрики ---
        total_int_base = df_base["Відсотки"].sum()
        total_int_real = df_real["Відсотки"].sum()
        saved_money = total_int_base - total_int_real

        months_base = len(df_base)
        months_real = len(df_real)
        saved_months = months_base - months_real
        
        # Обчислення років та місяців для відображення
        def format_duration(m):
            y = m // 12
            rem_m = m % 12
            if y > 0: return f"{y} р. {rem_m} міс."
            return f"{m} міс."

        col1, col2, col3 = st.columns(3)
        col1.metric("Загальні відсотки", f"{total_int_real:,.0f} грн", delta=f"-{saved_money:,.0f} грн", delta_color="inverse")
        col2.metric("Тривалість", format_duration(months_real), delta=f"-{saved_months} міс.", delta_color="inverse")
        
        first_pay = df_base.iloc[0]['Загальний платіж']
        col3.metric("Базовий платіж", f"{first_pay:,.2f} грн", help="Обов'язковий платіж без урахування додаткових погашень")

        # --- Графіки ---
        tab1, tab2, tab3 = st.tabs(["📉 Динаміка", "🍰 Аналіз", "📋 Таблиця"])

        with tab1:
            st.subheader("Порівняння швидкості погашення")
            df_chart = pd.concat([
                df_base[['Номер місяця', 'Залишок боргу']].assign(Сценарій="Базовий (без доплат)"),
                df_real[['Номер місяця', 'Залишок боргу']].assign(Сценарій="З достроковим погашенням")
            ])
            fig = px.line(df_chart, x="Номер місяця", y="Залишок боргу", color="Сценарій",
                          color_discrete_map={"Базовий (без доплат)": "#EF553B", "З достроковим погашенням": "#00CC96"})
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Структура витрат**")
                fig_pie = px.pie(names=['Тіло кредиту', 'Сплачені відсотки'], 
                                 values=[loan_amount, total_int_real], 
                                 hole=0.4, color_discrete_sequence=['#636EFA', '#EF553B'])
                st.plotly_chart(fig_pie, use_container_width=True)
            with c2:
                st.markdown("**Склад платежів у часі**")
                fig_bar = px.bar(df_real, x="Номер місяця", y=["Відсотки", "Тіло кредиту", "Додатково погашено"],
                                 labels={"value": "Сума (грн)"},
                                 color_discrete_map={"Відсотки": "#EF553B", "Тіло кредиту": "#636EFA", "Додатково погашено": "#00CC96"})
                st.plotly_chart(fig_bar, use_container_width=True)

        with tab3:
            st.dataframe(
                df_real.style.format({
                    "Загальний платіж": "{:,.2f}", 
                    "Тіло кредиту": "{:,.2f}",
                    "Відсотки": "{:,.2f}",
                    "Додатково погашено": "{:,.2f}",
                    "Залишок боргу": "{:,.2f}"
                }), 
                use_container_width=True
            )
            
            csv = df_real.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Завантажити CSV", data=csv, file_name="credit_schedule.csv", mime="text/csv")