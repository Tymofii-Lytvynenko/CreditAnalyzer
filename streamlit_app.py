import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
from dateutil.relativedelta import relativedelta

# --- Налаштування сторінки ---
st.set_page_config(
    page_title="Кредитний Калькулятор",
    page_icon="💸",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- CSS для мобільної оптимізації ---
st.markdown("""
    <style>
        .block-container {
            padding-top: 1rem;
            padding-bottom: 2rem;
            padding-left: 0.5rem;
            padding-right: 0.5rem;
        }
        [data-testid="stMetricValue"] {
            font-size: 1.1rem;
        }
         [data-testid="stMetricLabel"] {
            font-size: 0.8rem;
        }
        /* Зменшуємо заголовки на мобільному */
        h1 { font-size: 1.8rem; }
        h2 { font-size: 1.5rem; }
        h3 { font-size: 1.3rem; }
    </style>
""", unsafe_allow_html=True)

# --- Логіка розрахунку (Без змін) ---
@st.cache_data
def calculate_schedule(principal, annual_rate, start_date, 
                       years=None, fixed_payment=None, 
                       monthly_extra=0, irregular_payments=None):
    if irregular_payments is None:
        irregular_payments = {}

    monthly_rate = annual_rate / 12 / 100
    schedule = []
    remaining_balance = principal
    current_date = start_date
    
    if fixed_payment is not None:
        base_payment = fixed_payment
        first_month_interest = principal * monthly_rate
        if base_payment <= first_month_interest:
            return pd.DataFrame()
    else:
        total_months_planned = years * 12
        if monthly_rate > 0:
            base_payment = principal * (monthly_rate * (1 + monthly_rate)**total_months_planned) / ((1 + monthly_rate)**total_months_planned - 1)
        else:
            base_payment = principal / total_months_planned

    max_months = 600 
    
    for i in range(1, max_months + 1):
        if remaining_balance <= 0.01:
            break

        interest_payment = remaining_balance * monthly_rate
        current_base_payment = base_payment
        
        extra = monthly_extra
        if i in irregular_payments:
            extra += irregular_payments[i]
            
        total_payment_attempt = current_base_payment + extra
        
        if total_payment_attempt >= remaining_balance + interest_payment:
            total_payment = remaining_balance + interest_payment
            principal_payment = remaining_balance
            remaining_balance = 0
            extra_paid_in_record = max(0, total_payment - (interest_payment + (base_payment - interest_payment)))
        else:
            total_payment = total_payment_attempt
            principal_payment = total_payment - interest_payment
            remaining_balance -= principal_payment
            extra_paid_in_record = extra

        schedule.append({
            "Місяць": i,
            "Дата": current_date,
            "Платіж": total_payment,
            "Тіло": principal_payment,
            "Відсотки": interest_payment,
            "Extra": extra_paid_in_record,
            "Залишок": remaining_balance
        })
        
        current_date += relativedelta(months=1)

    return pd.DataFrame(schedule)

# --- Інтерфейс ---
st.title("💸 Кредитний Калькулятор")

# 1. Основні налаштування (Вгорі, в Expander для мобільних)
with st.expander("⚙️ Налаштування кредиту", expanded=True):
    # Використовуємо колонки для економії місця по вертикалі
    c_loan, c_rate = st.columns([2, 1])
    with c_loan:
        loan_amount = st.number_input("Сума кредиту (грн)", min_value=1000, value=500000, step=10000)
    with c_rate:
        interest_rate = st.number_input("Ставка (%)", min_value=0.1, value=15.0, step=0.5)
    
    start_date = st.date_input("Дата початку", value=date.today())
    
    # Радіокнопки горизонтально займають менше місця
    calc_mode = st.radio("Спосіб розрахунку:", ("За терміном", "За платежем"), horizontal=True, label_visibility="collapsed")

    target_years = None
    target_payment = None

    if calc_mode == "За терміном":
        target_years = st.slider("Термін (років):", 1, 30, 5)
    else:
        min_payment = (loan_amount * (interest_rate / 100 / 12)) + 1
        target_payment = st.number_input(
            f"Платіж (мін. {int(min_payment)} грн)", 
            min_value=float(int(min_payment)), 
            value=float(int(min_payment * 1.5)), 
            step=500.0
        )
    
    st.caption("ℹ️ Для додаткових погашень відкрийте бокове меню (зліва зверху).")

# 2. Sidebar (Тільки для просунутих налаштувань)
st.sidebar.header("🚀 Дострокове погашення")
monthly_extra_pay = st.sidebar.number_input("Щомісячна доплата (+грн)", min_value=0, value=0, step=500)

st.sidebar.subheader("Разові погашення")
irregular_data = pd.DataFrame([{"Місяць": 12, "Сума": 0}])
edited_df = st.sidebar.data_editor(irregular_data, num_rows="dynamic", hide_index=True)

irregular_payments_dict = {}
if not edited_df.empty:
    for _, row in edited_df.iterrows():
        try:
            m = int(row["Місяць"])
            val = float(row["Сума"])
            if m > 0 and val > 0:
                irregular_payments_dict[m] = irregular_payments_dict.get(m, 0) + val
        except:
            pass

# --- Розрахунки ---
valid_input = True
if target_payment is not None:
    monthly_rate_check = interest_rate / 12 / 100
    if target_payment <= loan_amount * monthly_rate_check:
        st.error(f"⚠️ Платіж замалий! Він не покриває відсотки. Мінімальний: {int(loan_amount * monthly_rate_check) + 1} грн")
        valid_input = False

if valid_input:
    with st.spinner("Рахуємо..."):
        # Базовий розрахунок
        df_base = calculate_schedule(loan_amount, interest_rate, start_date, years=target_years, fixed_payment=target_payment)
        # Реальний розрахунок
        df_real = calculate_schedule(
            loan_amount, interest_rate, start_date, 
            years=target_years, fixed_payment=target_payment,
            monthly_extra=monthly_extra_pay, irregular_payments=irregular_payments_dict
        )

    if df_real.empty:
        st.error("Помилка розрахунку. Перевірте вхідні дані.")
    else:
        # --- Метрики ---
        total_int_real = df_real["Відсотки"].sum()
        total_int_base = df_base["Відсотки"].sum()
        saved_money = total_int_base - total_int_real
        saved_months = len(df_base) - len(df_real)
        
        def fmt_yrs(m):
            y, rem = divmod(m, 12)
            if y > 0 and rem > 0: return f"{y}р {rem}м"
            if y > 0: return f"{y} років"
            return f"{m} міс"

        # Компактні метрики
        st.divider()
        # Використовуємо коротші назви для мобільного
        c1, c2, c3 = st.columns(3)
        c1.metric("Всього відсотків", f"{int(total_int_real):,} грн", delta=f"-{int(saved_money):,} грн", delta_color="inverse", help="Загальна переплата за кредитом")
        c2.metric("Реальний термін", fmt_yrs(len(df_real)), delta=f"-{saved_months} міс", delta_color="inverse")
        first_pay = df_base.iloc[0]['Платіж']
        c3.metric("Базовий платіж", f"{int(first_pay):,} грн", help="Ваш обов'язковий платіж за договором")
        st.divider()

        # --- Графіки та Таблиці ---
        # Відновлено 3 вкладки, як в оригіналі
        tab1, tab2, tab3 = st.tabs(["📉 Динаміка", "🍰 Аналіз", "📋 Таблиця"])

        with tab1:
            # Графік 1: Лінійний графік залишку
            df_chart = pd.concat([
                df_base[['Місяць', 'Залишок']].assign(Сценарій="Базовий (без доплат)"),
                df_real[['Місяць', 'Залишок']].assign(Сценарій="З достроковим погашенням")
            ])
            fig = px.line(df_chart, x="Місяць", y="Залишок", color="Сценарій",
                          color_discrete_map={"Базовий (без доплат)": "#EF553B", "З достроковим погашенням": "#00CC96"})
            
            # Легенда зверху горизонтально (краще для мобільного)
            fig.update_layout(
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(l=10, r=10, t=30, b=10),
                height=350,
                xaxis_title=None # Економимо місце
            )
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            # --- ВІДНОВЛЕНІ ГРАФІКИ ---
            # Вони тепер розташовані вертикально для мобільного, але зберегли вигляд.
            
            st.subheader("Структура витрат")
            # Той самий "гарний графік" з оригіналу
            fig_pie = px.pie(names=['Тіло кредиту', 'Сплачені відсотки'], 
                             values=[loan_amount, total_int_real], 
                             hole=0.4, color_discrete_sequence=['#636EFA', '#EF553B'])
            # Трохи зменшуємо поля для мобільного
            fig_pie.update_layout(margin=dict(t=20, b=20, l=10, r=10), height=300)
            st.plotly_chart(fig_pie, use_container_width=True)

            st.divider()
            
            st.subheader("Склад платежів у часі")
            # Другий графік з оригіналу
            fig_bar = px.bar(df_real, x="Місяць", y=["Відсотки", "Тіло", "Дострокові погашення"],
                             labels={"value": "Сума (грн)", "Місяць": "№ Місяця"},
                             color_discrete_map={"Відсотки": "#EF553B", "Тіло": "#636EFA", "Extra": "#00CC96"})
            # Легенда зверху
            fig_bar.update_layout(
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=None),
                margin=dict(l=10, r=10, t=30, b=10),
                height=350,
                xaxis_title=None # Економимо місце
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        with tab3:
            # Спрощена таблиця для мобільного
            mobile_df = df_real[["Дата", "Платіж", "Тіло", "Відсотки", "Extra", "Залишок"]].copy()
            # Форматування дати
            mobile_df["Дата"] = mobile_df["Дата"].apply(lambda x: x.strftime("%d.%m.%y"))
            
            st.dataframe(
                mobile_df.style.format("{:.0f}", subset=["Платіж", "Тіло", "Відсотки", "Extra", "Залишок"]), 
                use_container_width=True,
                height=450,
                hide_index=True
            )
            
            # Завантаження повної версії
            csv = df_real.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Завантажити повний CSV", data=csv, file_name="credit_schedule.csv", mime="text/csv")