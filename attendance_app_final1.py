import streamlit as st
import pandas as pd
from datetime import date, datetime

st.set_page_config(page_title="FYUGP Attendance App", layout="wide")
st.title("📘 FYUGP Attendance Management System")

@st.cache_data
def load_data():
    students = pd.read_csv("students.csv")
    courses = pd.read_csv("courses.csv")
    teachers = pd.read_csv("teachers.csv")
    try:
        attendance = pd.read_csv("attendance.csv")
    except FileNotFoundError:
        attendance = pd.DataFrame(columns=["date", "hour", "course_id", "student_id", "status", "marked_by", "extra_time", "duration"])
    try:
        camp_days = pd.read_csv("camp_days.csv", parse_dates=["start_date", "end_date"])
    except FileNotFoundError:
        camp_days = pd.DataFrame(columns=["student_id", "start_date", "end_date", "activity"])
    return students, courses, teachers, attendance, camp_days

students, courses, teachers, attendance, camp_days = load_data()

# Session Initialization
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# --------------------------
# 🔐 LOGIN SECTION
# --------------------------
if not st.session_state.logged_in:
    st.sidebar.header("🔐 Login")
    email = st.sidebar.text_input("Email").strip().lower()
    password = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Login"):
        match = teachers[
            (teachers["email"].str.strip().str.lower() == email) &
            (teachers["password"].astype(str).str.strip() == password)
        ]
        if not match.empty:
            st.session_state.logged_in = True
            st.session_state.teacher_id = match.iloc[0]["teacher_id"]
            st.session_state.teacher_name = match.iloc[0]["name"]
            st.session_state.role = match.iloc[0]["role"]
            st.session_state.department = match.iloc[0].get("department", "")
            st.sidebar.success(f"Welcome {st.session_state.teacher_name}")
        else:
            st.sidebar.error("Invalid login")

# --------------------------
# ✅ AFTER LOGIN
# --------------------------
else:
    st.sidebar.success(f"👋 {st.session_state.teacher_name}")
    if st.sidebar.button("🚪 Logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.experimental_rerun()

    # --------------------------
    # 📝 ATTENDANCE INTERFACE
    # --------------------------
    teacher_courses = courses[courses["teacher_id"] == st.session_state.teacher_id]
    if not teacher_courses.empty:
        st.subheader("📝 Take Attendance")
        selected_course = st.selectbox("Select your course:", teacher_courses["course_id"])

        if selected_course:
            enrolled = students[
                (students["major_course"] == selected_course) |
                (students["minor1_course"] == selected_course) |
                (students["minor2_course"] == selected_course) |
                (students["mdc_course"] == selected_course) |
                (students["vac_course"] == selected_course)
            ].copy()

            selected_date = st.date_input("Date for Attendance", value=date.today())

            # Get used hours
            existing_hours = attendance[
                (attendance["course_id"] == selected_course) &
                (attendance["date"] == str(selected_date))
            ]["hour"].dropna().unique().tolist()

            all_hours = [str(h) for h in range(1, 7)]
            available_hours = [h for h in all_hours if h not in existing_hours]
            available_hours.append("Extra Hour")

            selected_hour = st.selectbox("Select Hour (1–6 or Extra Hour)", options=available_hours)
            extra_time = ""
            duration = ""

            if selected_hour == "Extra Hour":
                extra_time = st.time_input("Start Time")
                duration = st.number_input("Duration (minutes)", min_value=10, max_value=180)

            # Attendance Status
            st.markdown("#### Set Special Status")
            student_labels = enrolled.apply(lambda x: f"{x['name']} ({x['student_id']})", axis=1).tolist()

            absent = st.multiselect("Absent (A)", student_labels)
            nss = st.multiselect("NSS", student_labels)
            ncc = st.multiselect("NCC", student_labels)
            club = st.multiselect("Club", student_labels)

            if st.button("💾 Save Attendance"):
                records = []
                for _, row in enrolled.iterrows():
                    sid = row["student_id"]
                    label = f"{row['name']} ({sid})"
                    if label in absent:
                        status = "A"
                    elif label in nss:
                        status = "NSS"
                    elif label in ncc:
                        status = "NCC"
                    elif label in club:
                        status = "Club"
                    else:
                        status = "P"

                    records.append({
                        "date": selected_date,
                        "hour": selected_hour,
                        "course_id": selected_course,
                        "student_id": sid,
                        "status": status,
                        "marked_by": st.session_state.teacher_id,
                        "extra_time": str(extra_time) if selected_hour == "Extra Hour" else "",
                        "duration": duration if selected_hour == "Extra Hour" else ""
                    })

                new_attendance = pd.DataFrame(records)

                # Overwrite existing entries
                attendance = attendance[~(
                    (attendance["date"] == str(selected_date)) &
                    (attendance["hour"] == selected_hour) &
                    (attendance["course_id"] == selected_course) &
                    (attendance["student_id"].isin(new_attendance["student_id"]))
                )]

                attendance = pd.concat([attendance, new_attendance], ignore_index=True)
                attendance.to_csv("attendance.csv", index=False)
                st.success("✅ Attendance saved successfully!")

    # -----------------------------
    # 🛡️ CAMP DAYS MANAGEMENT
    # -----------------------------
    if st.session_state.role in ["admin", "dept_admin"]:
        st.subheader("🛡 Camp Days Management")

        student_labels = students.apply(lambda x: f"{x['name']} ({x['student_id']})", axis=1).tolist()
        selected_student = st.selectbox("Select Student", student_labels)
        selected_id = selected_student.split("(")[-1].replace(")", "")

        start_camp = st.date_input("Start Date")
        end_camp = st.date_input("End Date")
        activity = st.selectbox("Activity", ["NSS", "NCC", "Club"])

        if st.button("➕ Add Camp Record"):
            new_camp = pd.DataFrame([{
                "student_id": selected_id,
                "start_date": pd.to_datetime(start_camp),
                "end_date": pd.to_datetime(end_camp),
                "activity": activity
            }])
            camp_days = pd.concat([camp_days, new_camp], ignore_index=True)
            camp_days.to_csv("camp_days.csv", index=False)
            st.success("✅ Camp record added.")

        # List and delete
        if not camp_days.empty:
            st.write("### 🧾 Existing Camp Records")
            for i, row in camp_days.iterrows():
                col1, col2 = st.columns([6, 1])
                with col1:
                    st.write(f"🧑‍🎓 {row['student_id']} | 🏷️ {row['activity']} | 📅 {row['start_date'].date()} → {row['end_date'].date()}")
                with col2:
                    if st.button("❌ Delete", key=f"del_camp_{i}"):
                        camp_days = camp_days.drop(i).reset_index(drop=True)
                        camp_days.to_csv("camp_days.csv", index=False)
                        st.experimental_rerun()
