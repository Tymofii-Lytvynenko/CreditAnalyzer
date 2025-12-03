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
        h1 { font-size: 1.8rem; }
        h2 { font-size: 1.5rem; }
        h3 { font-size: 1.3rem; }
    </style>
""", unsafe_allow_html=True)

# --- Логіка розрахунку ---
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
    
    # Визначення базового платежу
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
        # Додаємо ручні погашення з таблиці
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
            "Достроково": extra_paid_in_record, # Ця колонка для відображення факту
            "Залишок": remaining_balance
        })
        
        current_date += relativedelta(months=1)

    return pd.DataFrame(schedule)

# --- Інтерфейс ---
st.title("💸 Кредитний Калькулятор")

# 1. Основні налаштування
with st.expander("⚙️ Параметри кредиту", expanded=True):
    c_loan, c_rate = st.columns([2, 1])
    with c_loan:
        loan_amount = st.number_input("Сума кредиту (грн)", min_value=1000, value=500000, step=10000)
    with c_rate:
        interest_rate = st.number_input("Ставка (%)", min_value=0.1, value=15.0, step=0.5)
    
    start_date = st.date_input("Дата початку", value=date.today())
    
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

# Перевірка валідності для "За платежем"
valid_input = True
if target_payment is not None:
    monthly_rate_check = interest_rate / 12 / 100
    if target_payment <= loan_amount * monthly_rate_check:
        st.error(f"⚠️ Платіж замалий! Мінімальний: {int(loan_amount * monthly_rate_check) + 1} грн")
        valid_input = False

if valid_input:
    # --- КРОК 1: Базовий розрахунок ---
    # Спочатку рахуємо графік БЕЗ дострокових, щоб знати структуру таблиці
    df_base = calculate_schedule(loan_amount, interest_rate, start_date, years=target_years, fixed_payment=target_payment)

    # 2. Налаштування дострокових погашень (В головному меню)
    with st.expander("🚀 Дострокове погашення (Редагування таблиці)", expanded=False):
        st.caption("Введіть суми: регулярні (щомісяця) або точкові (прямо в таблиці).")
        
        # Глобальний щомісячний платіж
        monthly_extra_pay = st.number_input("Щомісячна доплата (+грн до кожного платежу)", min_value=0, value=0, step=500)
        
        st.divider()
        st.write("🗓 **Графік погашень (Редагуйте колонку 'Додати вручну')**")
        
        # Підготовка даних для редактора
        # Ми беремо базовий графік і додаємо пусту колонку для вводу користувача
        edit_prep_df = df_base[['Місяць', 'Дата', 'Платіж']].copy()
        edit_prep_df['Дата'] = edit_prep_df['Дата'].apply(lambda x: x.strftime("%d.%m.%Y"))
        edit_prep_df['Додати вручну'] = 0.0  # Колонка для редагування
        
        # Конфігурація редактора колонок
        column_config = {
            "Місяць": st.column_config.NumberColumn(disabled=True, width="small"),
            "Дата": st.column_config.TextColumn(disabled=True),
            "Платіж": st.column_config.NumberColumn("План. платіж", format="%d ₴", disabled=True),
            "Додати вручну": st.column_config.NumberColumn("Додати (+грн)", min_value=0, step=1000, required=True)
        }
        
        # ВІДОБРАЖЕННЯ ТАБЛИЦІ ДЛЯ РЕДАГУВАННЯ
        edited_schedule = st.data_editor(
            edit_prep_df, 
            column_config=column_config, 
            hide_index=True, 
            use_container_width=True,
            height=300,
            key="editor_key" # Важливо для збереження стану
        )
        
        # Збираємо дані з таблиці в словник {номер_місяця: сума}
        irregular_payments_dict = {}
        for index, row in edited_schedule.iterrows():
            if row['Додати вручну'] > 0:
                irregular_payments_dict[row['Місяць']] = row['Додати вручну']

    # --- КРОК 2: Фінальний розрахунок ---
    with st.spinner("Оновлюємо розрахунки..."):
        # Рахуємо реальний графік з урахуванням вводу користувача
        df_real = calculate_schedule(
            loan_amount, interest_rate, start_date, 
            years=target_years, fixed_payment=target_payment,
            monthly_extra=monthly_extra_pay, 
            irregular_payments=irregular_payments_dict
        )

    if df_real.empty:
        st.error("Помилка розрахунку.")
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

        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("Всього відсотків", f"{int(total_int_real):,} грн", delta=f"-{int(saved_money):,} грн", delta_color="inverse")
        c2.metric("Реальний термін", fmt_yrs(len(df_real)), delta=f"-{saved_months} міс", delta_color="inverse")
        first_pay = df_base.iloc[0]['Платіж']
        c3.metric("Базовий платіж", f"{int(first_pay):,} грн")
        st.divider()

        # --- Графіки та Таблиці ---
        tab1, tab2, tab3 = st.tabs(["📉 Порівняння", "🍰 Аналіз", "📋 Фінальна таблиця"])

        with tab1:
            # Лінійний графік залишку
            df_chart = pd.concat([
                df_base[['Місяць', 'Залишок']].assign(Сценарій="План (без доплат)"),
                df_real[['Місяць', 'Залишок']].assign(Сценарій="Факт (з доплатами)")
            ])
            fig = px.line(df_chart, x="Місяць", y="Залишок", color="Сценарій",
                          color_discrete_map={"План (без доплат)": "#EF553B", "Факт (з доплатами)": "#00CC96"})
            fig.update_layout(legend=dict(orientation="h", y=1.02, x=1), margin=dict(l=10, r=10, t=30, b=10), height=350, xaxis_title=None)
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            st.subheader("Структура витрат")
            fig_pie = px.pie(names=['Тіло кредиту', 'Сплачені відсотки'], 
                             values=[loan_amount, total_int_real], 
                             hole=0.4, color_discrete_sequence=['#636EFA', '#EF553B'])
            fig_pie.update_layout(margin=dict(t=20, b=20, l=10, r=10), height=300)
            st.plotly_chart(fig_pie, use_container_width=True)

            st.divider()
            st.subheader("Склад платежів")
            fig_bar = px.bar(df_real, x="Місяць", y=["Відсотки", "Тіло", "Достроково"],
                             labels={"value": "Сума (грн)", "Місяць": "№ Місяця"},
                             color_discrete_map={"Відсотки": "#EF553B", "Тіло": "#636EFA", "Достроково": "#00CC96"})
            fig_bar.update_layout(legend=dict(orientation="h", y=1.02, x=1, title=None), margin=dict(l=10, r=10, t=30, b=10), height=350, xaxis_title=None)
            st.plotly_chart(fig_bar, use_container_width=True)

        with tab3:
            # Фінальна таблиця результатів
            final_df = df_real[["Дата", "Платіж", "Тіло", "Відсотки", "Достроково", "Залишок"]].copy()
            final_df["Дата"] = final_df["Дата"].apply(lambda x: x.strftime("%d.%m.%y"))
            
            st.dataframe(
                final_df.style.format("{:.0f}", subset=["Платіж", "Тіло", "Відсотки", "Достроково", "Залишок"]), 
                use_container_width=True,
                height=450,
                hide_index=True
            )
            
            csv = df_real.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Завантажити CSV", data=csv, file_name="credit_schedule.csv", mime="text/csv")