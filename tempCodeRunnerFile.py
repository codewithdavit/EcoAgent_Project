
import streamlit as st
import pandas as pd
from io import BytesIO
from contextlib import closing

import db
import tools

st.set_page_config(
    page_title="EcoAgent — Smart Energy Assistant",
    page_icon="🌱",
    layout="wide"
)

db.init_db()

if "user" not in st.session_state:
    st.session_state.user = None


# =====================================================
# COMMON FUNCTIONS
# =====================================================

def logout():
    st.session_state.user = None
    st.rerun()


def show_login():
    st.title("🌱 EcoAgent — Smart Energy Assistant")
    st.caption(
        "Estimate household energy consumption, electricity "
        "cost and associated emissions."
    )

    login_tab, register_tab = st.tabs(["Login", "Create Account"])

    with login_tab:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button(
                "Login", type="primary", use_container_width=True
            )

        if submitted:
            user = db.authenticate(username, password)

            if user:
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Invalid username or password.")

    with register_tab:
        with st.form("register_form"):
            new_username = st.text_input("Choose username")
            new_password = st.text_input(
                "Choose password (minimum 6 characters)",
                type="password"
            )
            state = st.selectbox("State", db.STATES)

            register = st.form_submit_button(
                "Create Account",
                type="primary",
                use_container_width=True
            )

        if register:
            ok, message = db.register_user(
                new_username, new_password, state
            )
            if ok:
                st.success(message)
            else:
                st.error(message)


# =====================================================
# USER DASHBOARD
# =====================================================

def show_user_dashboard(user):
    st.title("🌱 EcoAgent — Personal Energy Assistant")

    with st.sidebar:
        st.subheader(f"Welcome, {user['username']}")
        st.write(f"State: {user.get('state') or 'Not set'}")
        st.write("Role: User")

        if st.button("Logout", use_container_width=True):
            logout()

    usage_tab, summary_tab, tips_tab, report_tab = st.tabs([
        "⚡ Energy Usage",
        "📊 Monthly & Yearly Summary",
        "🌿 Recommendations",
        "📄 My Report"
    ])

    with usage_tab:
        st.subheader("Estimate Appliance Energy Consumption")

        c1, c2 = st.columns(2)

        with c1:
            appliance = st.selectbox(
                "Appliance",
                [
                    "Air Conditioner", "Refrigerator",
                    "Washing Machine", "Television", "Fan",
                    "LED Bulb", "Water Heater", "Laptop",
                    "Microwave", "Other"
                ]
            )

            hours = st.number_input(
                "Hours used per day",
                min_value=0.0, max_value=24.0,
                value=2.0, step=0.5
            )

            quantity = st.number_input(
                "Number of appliances",
                min_value=1, max_value=100, value=1
            )

        with c2:
            watts = st.number_input(
                "Power rating (watts)",
                min_value=1.0, max_value=20000.0,
                value=100.0, step=10.0
            )

            temperature = st.number_input(
                "Outdoor temperature (°C)",
                min_value=-10.0, max_value=55.0,
                value=25.0
            )

            if st.button("Get Live Weather"):
                try:
                    weather = tools.get_live_weather(user.get("state"))
                    st.session_state.weather_temp = weather["temperature"]
                    st.success(
                        f"{weather['place']}: "
                        f"{weather['temperature']} °C"
                    )
                except Exception as error:
                    st.warning(f"Weather unavailable: {error}")

        if st.button("Predict and Save Usage", type="primary"):
            try:
                temperature = st.session_state.get(
                    "weather_temp", temperature
                )

                ml_prediction = tools.predict_kwh(
                    hours, quantity, watts, temperature
                )

                formula_estimate = hours * quantity * watts / 1000

                # Combine ML estimate with the physical energy formula.
                kwh = max(
                    0.0,
                    0.5 * ml_prediction + 0.5 * formula_estimate
                )

                cost = tools.calculate_cost(kwh, user.get("state"))

                db.save_usage(
                    user["id"], appliance, hours,
                    quantity, watts, kwh, cost
                )

                st.success(
                    f"Estimated energy: {kwh:.3f} kWh/day | "
                    f"Estimated cost: ₹{cost:.2f}/day"
                )
                st.rerun()

            except Exception as error:
                st.error(f"Prediction failed: {error}")

        records = db.get_usage(user["id"])

        st.subheader("My Saved Appliance Records")

        if records.empty:
            st.info("No records yet. Add an appliance above.")
        else:
            st.dataframe(records, hide_index=True, use_container_width=True)
            st.bar_chart(
                records.groupby("appliance")["kwh"]
                .sum().sort_values(ascending=False)
            )

    records = db.get_usage(user["id"])
    summary = tools.calculate_summary(records, user.get("state"))

    db.save_summary(user["id"], **summary)

    with summary_tab:
        a, b, c = st.columns(3)

        a.metric("Monthly Energy", f"{summary['monthly_kwh']:,.2f} kWh")
        b.metric("Monthly Cost", f"₹{summary['monthly_cost']:,.2f}")
        c.metric("Monthly CO₂", f"{summary['co2_kg']:,.2f} kg")

        d, e = st.columns(2)
        d.metric("Yearly Energy", f"{summary['yearly_kwh']:,.2f} kWh")
        e.metric("Yearly Cost", f"₹{summary['yearly_cost']:,.2f}")

        st.caption(
            "Estimates extrapolate the saved daily usage over "
            "30 days and 365 days."
        )

    with tips_tab:
        st.subheader("Energy-Saving Recommendations")
        for tip in tools.recommendations(records):
            st.write("• " + tip)

        st.info(
            "CO₂ is estimated using a simplified factor of "
            "0.708 kg per kWh."
        )

    with report_tab:
        st.subheader("Download My Report")

        if not records.empty:
            st.download_button(
                "Download Usage CSV",
                records.to_csv(index=False).encode("utf-8"),
                "ecoagent_usage.csv",
                "text/csv"
            )

        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table
            )
            from reportlab.lib.styles import getSampleStyleSheet

            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
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
                )
            ]

            if not records.empty:
                table_data = [[
                    "Appliance", "Hours", "Qty", "Watts", "kWh/day", "Cost/day"
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

                story.extend([Spacer(1, 15), Table(table_data, repeatRows=1)])

            doc.build(story)

            st.download_button(
                "Download PDF Report",
                buffer.getvalue(),
                "ecoagent_report.pdf",
                "application/pdf"
            )

        except ImportError:
            st.warning("Install reportlab to enable PDF reports.")


# =====================================================
# ADMIN DASHBOARD
# =====================================================

def show_admin_dashboard(user):
    st.title("🛠️ EcoAgent — Admin Dashboard")

    with st.sidebar:
        st.subheader(f"Welcome, {user['username']}")
        st.write("Role: Administrator")

        if st.button("Logout", use_container_width=True):
            logout()

    users = db.list_users()
    users = users[users["role"] == "user"].copy()

    with closing(db._conn()) as conn:
        records = pd.read_sql_query("""
            SELECT
                u.id AS user_id,
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
        """, conn)

    summary = db.admin_summary()

    # TOP METRICS
    c1, c2, c3 = st.columns(3)

    c1.metric("Registered Users", len(users))
    c2.metric(
        "States With Users",
        users["state"].nunique() if not users.empty else 0
    )
    c3.metric(
        "Estimated Yearly Cost",
        f"₹{summary['yearly_cost'].sum():,.2f}"
        if not summary.empty else "₹0.00"
    )

    dashboard_tab, users_tab, forecast_tab = st.tabs([
        "📊 Dashboard",
        "👥 All Users & Records",
        "⚡ State-wise Yearly Forecast"
    ])

    # DASHBOARD
    with dashboard_tab:
        st.subheader("Registered Users by State")

        if users.empty:
            st.info("No registered users available.")
        else:
            st.bar_chart(users.groupby("state").size())

        st.subheader("Yearly Energy by State")

        if not summary.empty:
            st.bar_chart(
                summary.groupby("state")["yearly_kwh"]
                .sum().sort_values(ascending=False)
            )

        st.subheader("Yearly Cost by State")

        if not summary.empty:
            st.bar_chart(
                summary.groupby("state")["yearly_cost"]
                .sum().sort_values(ascending=False)
            )

    # USER RECORDS
    with users_tab:
        st.subheader("All Registered Users")
        st.dataframe(users, hide_index=True, use_container_width=True)

        st.subheader("Recorded Appliance Usage")

        if records.empty:
            st.info("No saved energy records available.")
        else:
            states = ["All States"] + sorted(
                records["state"].dropna().unique().tolist()
            )

            selected_state = st.selectbox(
                "Filter records by state",
                states
            )

            filtered = records.copy()

            if selected_state != "All States":
                filtered = filtered[filtered["state"] == selected_state]

            st.dataframe(
                filtered, hide_index=True, use_container_width=True
            )

            st.download_button(
                "Download User Records CSV",
                filtered.to_csv(index=False).encode("utf-8"),
                "ecoagent_all_user_records.csv",
                "text/csv"
            )

        st.subheader("Delete User")

        if not users.empty:
            user_choices = {
                f"{row.username} — {row.state} (ID {row.id})": row.id
                for row in users.itertuples()
            }

            selected_user = st.selectbox(
                "Select user to delete",
                list(user_choices.keys()),
                key="delete_user_select"
            )

            confirm = st.checkbox(
                "I confirm that this user's records should be deleted."
            )

            if st.button("Delete Selected User", type="primary"):
                if confirm:
                    db.delete_user(user_choices[selected_user])
                    st.success("User and related records deleted.")
                    st.rerun()
                else:
                    st.warning("Please confirm before deleting.")

    # STATE-WISE FORECAST
    with forecast_tab:
        st.subheader("State-wise Estimated Yearly Energy Cost")

        st.caption(
            "This is an estimate based on registered users' saved "
            "usage summaries, not the actual total electricity demand "
            "of an entire state."
        )

        if summary.empty:
            st.info(
                "No user summaries available. Users must save "
                "appliance records first."
            )
        else:
            forecast = (
                summary.groupby("state", dropna=False)
                .agg(
                    Users=("username", "nunique"),
                    **{
                        "Yearly Energy (kWh)": ("yearly_kwh", "sum"),
                        "Saved Yearly Cost (₹)": ("yearly_cost", "sum")
                    }
                )
                .reset_index()
                .rename(columns={"state": "State"})
            )

            forecast["State"] = forecast["State"].fillna("Unknown")

            forecast["Tariff (₹/kWh)"] = forecast["State"].map(
                db.STATE_TARIFF
            ).fillna(7.0)

            # Estimate cost from annual energy and configured state tariff.
            forecast["Estimated Yearly Cost (₹)"] = (
                forecast["Yearly Energy (kWh)"]
                * forecast["Tariff (₹/kWh)"]
            )

            forecast = forecast.sort_values(
                "Estimated Yearly Cost (₹)",
                ascending=False
            )

            st.dataframe(
                forecast.style.format({
                    "Yearly Energy (kWh)": "{:,.2f}",
                    "Saved Yearly Cost (₹)": "₹{:,.2f}",
                    "Tariff (₹/kWh)": "₹{:,.2f}",
                    "Estimated Yearly Cost (₹)": "₹{:,.2f}"
                }),
                hide_index=True,
                use_container_width=True
            )

            st.subheader("Estimated Yearly Cost by State")
            st.bar_chart(
                forecast.set_index("State")["Estimated Yearly Cost (₹)"]
            )

            st.subheader("Estimated Yearly Energy by State")
            st.bar_chart(
                forecast.set_index("State")["Yearly Energy (kWh)"]
            )

            st.download_button(
                "Download State Forecast CSV",
                forecast.to_csv(index=False).encode("utf-8"),
                "ecoagent_state_yearly_forecast.csv",
                "text/csv"
            )


# =====================================================
# APPLICATION ROUTER
# =====================================================

if st.session_state.user is None:
    show_login()
else:
    current_user = st.session_state.user

    # Refresh role and account details from the database.
    latest_user = db.get_user_by_name(current_user["username"])

    if latest_user is None:
        st.session_state.user = None
        st.error("This account no longer exists. Please log in again.")
        st.rerun()

    elif latest_user["role"] == "admin":
        show_admin_dashboard(latest_user)

    else:
        show_user_dashboard(latest_user)