import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
from dateutil.relativedelta import relativedelta

# --- Налаштування сторінки ---
st.set_page_config(
    page_title="Кредитний Калькулятор",
    page_icon="💸",
    layout="centered",  # "centered" краще виглядає на мобільних телефонах, ніж "wide"
    initial_sidebar_state="collapsed"
)

# --- CSS для мобільної оптимізації ---
# Зменшуємо відступи, щоб контент краще влазив на екран
st.markdown("""
    <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
            padding-left: 1rem;
            padding-right: 1rem;
        }
        [data-testid="stMetricValue"] {
            font-size: 1.2rem;
        }
    </style>
""", unsafe_allow_html=True)

# --- Логіка розрахунку (Без змін, вона правильна) ---
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
    col_in1, col_in2 = st.columns(2)
    with col_in1:
        loan_amount = st.number_input("Сума (грн)", min_value=1000, value=500000, step=10000)
    with col_in2:
        interest_rate = st.number_input("Ставка (%)", min_value=0.1, value=15.0, step=0.5)
    
    start_date = st.date_input("Дата початку", value=date.today())
    
    calc_mode = st.radio("Розрахунок за:", ("Терміном", "Платежем"), horizontal=True)

    target_years = None
    target_payment = None

    if calc_mode == "Терміном":
        target_years = st.slider("Років:", 1, 30, 5)
    else:
        min_payment = (loan_amount * (interest_rate / 100 / 12)) + 1
        target_payment = st.number_input(
            f"Платіж (мін. {int(min_payment)} грн)", 
            min_value=float(int(min_payment)), 
            value=float(int(min_payment * 1.5)), 
            step=500.0
        )
    
    st.caption("👇 Для дод. погашень відкрийте бокове меню (зліва зверху).")

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
        st.error(f"⚠️ Платіж замалий! Мінімальний: {int(loan_amount * monthly_rate_check) + 1} грн")
        valid_input = False

if valid_input:
    # Базовий розрахунок
    df_base = calculate_schedule(loan_amount, interest_rate, start_date, years=target_years, fixed_payment=target_payment)
    # Реальний розрахунок
    df_real = calculate_schedule(
        loan_amount, interest_rate, start_date, 
        years=target_years, fixed_payment=target_payment,
        monthly_extra=monthly_extra_pay, irregular_payments=irregular_payments_dict
    )

    if df_real.empty:
        st.error("Помилка розрахунку.")
    else:
        # --- Метрики ---
        total_int_real = df_real["Відсотки"].sum()
        total_int_base = df_base["Відсотки"].sum()
        saved_money = total_int_base - total_int_real
        saved_months = len(df_base) - len(df_real)
        
        # Функція форматування років
        def fmt_yrs(m):
            y, rem = divmod(m, 12)
            return f"{y}р {rem}м" if y > 0 else f"{m} міс"

        # Компактні метрики
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("Відсотки", f"{int(total_int_real/1000)}k", delta=f"-{int(saved_money)} грн", delta_color="inverse")
        c2.metric("Термін", fmt_yrs(len(df_real)), delta=f"-{saved_months} міс", delta_color="inverse")
        first_pay = df_base.iloc[0]['Платіж']
        c3.metric("База", f"{int(first_pay)}")
        st.divider()

        # --- Графіки (Оптимізовано для мобільних) ---
        tab1, tab2 = st.tabs(["📉 Графік", "📋 Таблиця"])

        with tab1:
            # Графік 1: Залишок
            df_chart = pd.concat([
                df_base[['Місяць', 'Залишок']].assign(Тип="План"),
                df_real[['Місяць', 'Залишок']].assign(Тип="Факт")
            ])
            fig = px.line(df_chart, x="Місяць", y="Залишок", color="Тип",
                          color_discrete_map={"План": "#EF553B", "Факт": "#00CC96"})
            
            # Легенда зверху для економії місця
            fig.update_layout(
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(l=10, r=10, t=30, b=10),
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)

            # Графік 2: Структура (Pie)
            st.caption("Структура виплат:")
            fig_pie = px.pie(names=['Тіло', 'Відсотки'], values=[loan_amount, total_int_real], 
                             hole=0.5, color_discrete_sequence=['#636EFA', '#EF553B'])
            fig_pie.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=250, showlegend=False)
            # Додаємо текст в центр
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_pie, use_container_width=True)

        with tab2:
            # Спрощена таблиця для мобільного
            mobile_df = df_real[["Дата", "Платіж", "Тіло", "Відсотки", "Залишок"]].copy()
            # Форматування дати
            mobile_df["Дата"] = mobile_df["Дата"].apply(lambda x: x.strftime("%d.%m.%y"))
            
            st.dataframe(
                mobile_df.style.format("{:.0f}", subset=["Платіж", "Тіло", "Відсотки", "Залишок"]), 
                use_container_width=True,
                height=400
            )
            
            # Завантаження повної версії
            csv = df_real.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Завантажити повний CSV", data=csv, file_name="credit.csv", mime="text/csv")