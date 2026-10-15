import streamlit as st
import pandas as pd
import db
import tools

st.set_page_config(
    page_title="EcoAgent",
    page_icon="🌱",
    layout="wide"
)

db.init_db()

if "user" not in st.session_state:
    st.session_state.user = None

if "admin_user" not in st.session_state:
    st.session_state.admin_user = None

st.title("🌱 EcoAgent — Smart Energy Assistant")
st.caption(
    "Estimate household energy consumption, electricity cost "
    "and associated emissions."
)

# =====================================================
# LOGIN / REGISTER / ADMIN LOGIN
# =====================================================

if (
    st.session_state.user is None
    and st.session_state.admin_user is None
):

    login_tab, register_tab, admin_tab = st.tabs(
        ["Login", "Create account", "Admin"]
    )

    with login_tab:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input(
                "Password",
                type="password"
            )

            submitted = st.form_submit_button(
                "Login",
                type="primary",
                use_container_width=True
            )

        if submitted:
            user = db.authenticate(username, password)

            if user and user["role"] == "user":
                st.session_state.user = user
                st.rerun()

            elif user and user["role"] == "admin":
                st.info("Please use the Admin tab.")

            else:
                st.error("Invalid username or password.")

    with register_tab:
        with st.form("register_form"):
            new_user = st.text_input("Choose username")

            new_pass = st.text_input(
                "Choose password (at least 6 characters)",
                type="password"
            )

            state = st.selectbox(
                "State / UT",
                db.STATES
            )

            register = st.form_submit_button(
                "Create account",
                type="primary",
                use_container_width=True
            )

        if register:
            ok, message = db.register_user(
                new_user,
                new_pass,
                state
            )

            if ok:
                st.success(message)
            else:
                st.error(message)

    with admin_tab:
        st.subheader("Administrator Login")

        st.write(
            "View registered users, saved energy records "
            "and state-wise yearly cost estimates."
        )

        with st.form("admin_login_form"):
            admin_username = st.text_input(
                "Admin username"
            )

            admin_password = st.text_input(
                "Admin password",
                type="password"
            )

            admin_submit = st.form_submit_button(
                "Open Admin Dashboard",
                type="primary",
                use_container_width=True
            )

        if admin_submit:
            admin = db.authenticate(
                admin_username,
                admin_password
            )

            if admin and admin.get("role") == "admin":
                st.session_state.admin_user = admin
                st.rerun()
            else:
                st.error("Invalid admin credentials.")

        st.caption("Demo login: admin / admin123")

    st.stop()


# =====================================================
# ADMIN DASHBOARD
# =====================================================

if (
    st.session_state.admin_user is not None
    and st.session_state.user is None
):

    st.title("🛠️ EcoAgent Admin Dashboard")

    if st.button("Admin Logout"):
        st.session_state.admin_user = None
        st.rerun()

    users = db.list_users()

    normal_users = users[
        users["role"] == "user"
    ].copy()

    summaries = db.admin_summary()

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Registered Users",
        len(normal_users)
    )

    c2.metric(
        "States Represented",
        int(normal_users["state"].nunique())
        if not normal_users.empty else 0
    )

    c3.metric(
        "Estimated Monthly Energy",
        f"{summaries['monthly_kwh'].sum():,.1f} kWh"
    )

    c4.metric(
        "Estimated Yearly Cost",
        f"₹{summaries['yearly_cost'].sum():,.0f}"
    )

    overview_tab, records_tab, state_tab = st.tabs(
        [
            "📊 Overview",
            "👥 All Users & Records",
            "⚡ State-wise Yearly Cost"
        ]
    )

    # -------------------------------------------------
    # OVERVIEW
    # -------------------------------------------------

    with overview_tab:
        st.subheader("Registered Users by State")

        state_users = db.state_summary()

        if state_users.empty:
            st.info("No registered users yet.")
        else:
            st.dataframe(
                state_users,
                hide_index=True,
                use_container_width=True
            )

            st.bar_chart(
                state_users.set_index("state")["users"]
            )

        st.subheader("Energy Summary of Every User")

        if summaries.empty:
            st.info("No energy summaries available.")
        else:
            st.dataframe(
                summaries,
                hide_index=True,
                use_container_width=True
            )

    # -------------------------------------------------
    # ALL USERS AND RECORDS
    # -------------------------------------------------

    with records_tab:
        st.subheader("All Registered Accounts")

        st.dataframe(
            users,
            hide_index=True,
            use_container_width=True
        )

        with db._conn() as conn:
            records = pd.read_sql_query(
                """
                SELECT
                    u.username,
                    u.state,
                    x.appliance,
                    x.hours,
                    x.quantity,
                    x.watts,
                    x.kwh,
                    x.cost,
                    x.created_at
                FROM usage x
                JOIN users u ON u.id = x.user_id
                WHERE u.role = 'user'
                ORDER BY u.state, u.username, x.created_at DESC
                """,
                conn
            )

        st.subheader("Recorded Energy Data")

        if records.empty:
            st.info(
                "No saved records. Users must save appliance "
                "usage from their account first."
            )
        else:
            states = (
                ["All states"]
                + sorted(records["state"].dropna().unique().tolist())
            )

            selected_state = st.selectbox(
                "Filter by State",
                states
            )

            filtered = (
                records
                if selected_state == "All states"
                else records[records["state"] == selected_state]
            )

            st.dataframe(
                filtered,
                hide_index=True,
                use_container_width=True
            )

            st.download_button(
                "Download User Records CSV",
                filtered.to_csv(index=False).encode("utf-8"),
                file_name="ecoagent_user_records.csv",
                mime="text/csv"
            )

    # -------------------------------------------------
    # STATE-WISE YEARLY COST
    # -------------------------------------------------

    with state_tab:
        st.subheader("State-wise Estimated Yearly Electricity Cost")

        if summaries.empty:
            st.info(
                "No saved energy summaries. Register users and "
                "save appliance usage first."
            )
        else:
            forecast = []

            for state, group in summaries.groupby(
                "state",
                dropna=False
            ):
                state_name = (
                    state
                    if pd.notna(state) and str(state).strip()
                    else "Unknown"
                )

                tariff = db.STATE_TARIFF.get(
                    state_name,
                    7.0
                )

                yearly_kwh = float(
                    group["yearly_kwh"].sum()
                )

                yearly_cost = yearly_kwh * tariff

                forecast.append({
                    "State": state_name,
                    "Users": int(group["username"].nunique()),
                    "Yearly Energy (kWh)": yearly_kwh,
                    "Tariff (₹/kWh)": tariff,
                    "Estimated Yearly Cost (₹)": yearly_cost
                })

            forecast_df = pd.DataFrame(forecast)

            forecast_df = forecast_df.sort_values(
                "Estimated Yearly Cost (₹)",
                ascending=False
            )

            st.dataframe(
                forecast_df,
                hide_index=True,
                use_container_width=True
            )

            st.bar_chart(
                forecast_df.set_index("State")[
                    "Estimated Yearly Cost (₹)"
                ]
            )

            st.download_button(
                "Download State-wise Forecast CSV",
                forecast_df.to_csv(index=False).encode("utf-8"),
                file_name="ecoagent_state_yearly_forecast.csv",
                mime="text/csv"
            )

        st.caption(
            "These are estimates based on registered users' saved "
            "energy records, not the total electricity consumption "
            "of each state. Verify the demo tariffs before using "
            "the figures as actual billing estimates."
        )

    st.stop()


# =====================================================
# USER DASHBOARD
# =====================================================

user = st.session_state.user

with st.sidebar:
    st.subheader(f"Welcome, {user['username']}")
    st.write("State:", user.get("state") or "Not set")

    if st.button("Logout", use_container_width=True):
        st.session_state.user = None
        st.rerun()


usage_tab, summary_tab, tips_tab, report_tab = st.tabs(
    [
        "⚡ Energy Usage",
        "📈 Monthly & Yearly Summary",
        "🌿 Recommendations",
        "📄 My Report"
    ]
)


# =====================================================
# ENERGY USAGE
# =====================================================

with usage_tab:
    st.subheader("Estimate an Appliance")

    st.write(
        "Enter typical daily usage. Values are estimates, "
        "not readings from a utility meter."
    )

    col1, col2 = st.columns(2)

    with col1:
        appliance = st.selectbox(
            "Appliance",
            [
                "Air Conditioner",
                "Refrigerator",
                "Washing Machine",
                "Television",
                "Fan",
                "LED Bulb",
                "Water Heater",
                "Laptop",
                "Microwave",
                "Other"
            ]
        )

        hours = st.number_input(
            "Hours used per day",
            min_value=0.0,
            max_value=24.0,
            value=2.0,
            step=0.5
        )

        quantity = st.number_input(
            "Number of appliances",
            min_value=1,
            max_value=100,
            value=1
        )

    with col2:
        if st.button("Get Live Weather"):
            try:
                weather = tools.get_live_weather(
                    user.get("state")
                )

                st.session_state["ecoagent_weather_temp"] = (
                    weather["temperature"]
                )

                st.session_state["ecoagent_weather_label"] = (
                    f"{weather['place']}: "
                    f"{weather['temperature']} °C"
                )

            except Exception as exc:
                st.warning(f"Weather unavailable: {exc}")

        if st.session_state.get("ecoagent_weather_label"):
            st.caption(
                st.session_state["ecoagent_weather_label"]
            )

        watts = st.number_input(
            "Power rating (watts)",
            min_value=1.0,
            max_value=20000.0,
            value=100.0,
            step=10.0
        )

        temperature = st.number_input(
            "Outdoor temperature (°C)",
            min_value=-10.0,
            max_value=55.0,
            value=float(
                st.session_state.get(
                    "ecoagent_weather_temp",
                    25.0
                )
            ),
            step=1.0
        )

        tariff = db.STATE_TARIFF.get(
            user.get("state"),
            7.0
        )

        st.caption(
            f"Configured demo tariff: ₹{tariff:.2f}/kWh"
        )

    if st.button("Predict and Save Usage", type="primary"):
        try:
            predicted = tools.predict_kwh(
                hours,
                quantity,
                watts,
                temperature
            )

            # Basic physics-based daily estimate
            physics_kwh = hours * quantity * watts / 1000

            # Blend the ML estimate with the physical estimate
            kwh = max(
                0.0,
                0.5 * predicted + 0.5 * physics_kwh
            )

            cost = tools.calculate_cost(
                kwh,
                user.get("state")
            )

            db.save_usage(
                user["id"],
                appliance,
                hours,
                quantity,
                watts,
                kwh,
                cost
            )

            st.success(
                f"Saved: {kwh:.3f} kWh/day; "
                f"estimated cost ₹{cost:.2f}/day."
            )

            st.rerun()

        except Exception as exc:
            st.error(f"Prediction failed: {exc}")

    records = db.get_usage(user["id"])

    st.subheader("Saved Appliance Records")

    if records.empty:
        st.info("No records yet. Add your first appliance.")
    else:
        st.dataframe(
            records,
            hide_index=True,
            use_container_width=True
        )

        st.bar_chart(
            records.groupby("appliance")["kwh"]
            .sum()
            .sort_values(ascending=False)
        )


# =====================================================
# SUMMARY CALCULATIONS
# =====================================================

records = db.get_usage(user["id"])

summary = tools.calculate_summary(
    records,
    user.get("state")
)

db.save_summary(
    user["id"],
    **summary
)


# =====================================================
# MONTHLY / YEARLY SUMMARY
# =====================================================

with summary_tab:
    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Monthly Energy",
        f"{summary['monthly_kwh']:.1f} kWh"
    )

    col2.metric(
        "Monthly Cost",
        f"₹{summary['monthly_cost']:,.0f}"
    )

    col3.metric(
        "Monthly CO₂",
        f"{summary['co2_kg']:,.1f} kg"
    )

    col4, col5 = st.columns(2)

    col4.metric(
        "Yearly Energy",
        f"{summary['yearly_kwh']:,.1f} kWh"
    )

    col5.metric(
        "Yearly Cost",
        f"₹{summary['yearly_cost']:,.0f}"
    )

    st.caption(
        "Monthly and yearly estimates extrapolate saved daily "
        "usage over 30 and 365 days."
    )


# =====================================================
# RECOMMENDATIONS
# =====================================================

with tips_tab:
    st.subheader("Personalized Energy-Saving Suggestions")

    for tip in tools.recommendations(records):
        st.write("• " + tip)

    st.info(
        "CO₂ is estimated using a simplified factor of "
        "0.708 kg per kWh."
    )


# =====================================================
# REPORTS
# =====================================================

with report_tab:
    st.subheader("Download My Report")

    if not records.empty:
        st.download_button(
            "Download Usage Records (CSV)",
            records.to_csv(index=False).encode("utf-8"),
            file_name="ecoagent_usage.csv",
            mime="text/csv"
        )

    try:
        from io import BytesIO
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table
        )
        from reportlab.lib.styles import getSampleStyleSheet

        buffer = BytesIO()

        document = SimpleDocTemplate(
            buffer,
            pagesize=A4
        )

        styles = getSampleStyleSheet()

        story = [
            Paragraph("EcoAgent Energy Report", styles["Title"]),
            Spacer(1, 12),
            Paragraph(
                f"User: {user['username']} | "
                f"State: {user.get('state', '')}",
                styles["Normal"]
            ),
            Spacer(1, 12),
            Paragraph(
                f"Monthly energy: {summary['monthly_kwh']:.2f} kWh",
                styles["Normal"]
            ),
            Paragraph(
                f"Monthly cost: Rs. {summary['monthly_cost']:.2f}",
                styles["Normal"]
            ),
            Paragraph(
                f"Yearly energy: {summary['yearly_kwh']:.2f} kWh",
                styles["Normal"]
            ),
            Paragraph(
                f"Yearly cost: Rs. {summary['yearly_cost']:.2f}",
                styles["Normal"]
            ),
            Paragraph(
                f"Monthly CO2 estimate: {summary['co2_kg']:.2f} kg",
                styles["Normal"]
            )
        ]

        if not records.empty:
            table_data = [[
                "Appliance",
                "Hours/day",
                "Quantity",
                "Watts",
                "kWh/day",
                "Cost/day"
            ]]

            for _, row in records.iterrows():
                table_data.append([
                    str(row["appliance"]),
                    str(row["hours"]),
                    str(row["quantity"]),
                    str(row["watts"]),
                    f"{row['kwh']:.3f}",
                    f"{row['cost']:.2f}"
                ])

            story.extend([
                Spacer(1, 16),
                Table(table_data, repeatRows=1)
            ])

        document.build(story)

        st.download_button(
            "Download PDF Report",
            buffer.getvalue(),
            file_name="ecoagent_report.pdf",
            mime="application/pdf"
        )

    except ImportError:
        st.warning(
            "Install reportlab to enable PDF reports: "
            "python -m pip install reportlab"
        )