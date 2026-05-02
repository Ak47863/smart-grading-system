import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm
import pdfplumber
from io import BytesIO

# -------------------------------------------------
# Page Setup
# -------------------------------------------------

st.set_page_config(
    page_title="Smart Automated Grading System",
    layout="wide"
)

# st.title("Smart Automated Grading System")

# -------------------------------------------------
# Color Editing Panel
# -------------------------------------------------

st.sidebar.header("UI & Color Settings")

primary_color = st.sidebar.color_picker("Primary Theme Color", "#581fb4")
hist_color = st.sidebar.color_picker("Histogram Color", "#5A21DD")
bell_color = st.sidebar.color_picker("Bell Curve Color", "#E9253F")
bar_color = st.sidebar.color_picker("Bar Chart Color", "#E7196F")
pass_color = st.sidebar.color_picker("Pass Highlight Color", "#DFF5E1")
risk_color = st.sidebar.color_picker("At-Risk Highlight Color", "#CF1C94")

st.markdown(
    f"""
    <h1 style='text-align:center; color:{primary_color};'>
        Smart Automated Grading System
    </h1>
    """,
    unsafe_allow_html=True
)

st.markdown(
    f"""
    <style>
    h1, h2, h3 {{
        color: {primary_color};
    }}

    .stButton button {{
        background-color: {primary_color};
        color: white;
        border-radius: 8px;
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# -------------------------------------------------
# Column Detection
# -------------------------------------------------

NON_GRADING_KEYWORDS = [
    "name", "roll", "email", "registration", "reg", "id",
    "student", "section", "branch", "department"
]

GRADING_KEYWORDS = [
    "quiz", "mid", "midterm", "end", "endterm", "exam",
    "assignment", "lab", "project", "presentation", "test"
]


def detect_columns(df):
    non_grading = []
    grading = []

    for col in df.columns:
        col_lower = str(col).lower()

        if any(key in col_lower for key in NON_GRADING_KEYWORDS):
            non_grading.append(col)

        elif any(key in col_lower for key in GRADING_KEYWORDS):
            grading.append(col)

        elif pd.api.types.is_numeric_dtype(df[col]):
            grading.append(col)

        else:
            non_grading.append(col)

    return non_grading, grading


# -------------------------------------------------
# PDF Reading
# -------------------------------------------------

def read_pdf(file):
    all_tables = []

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()

            for table in tables:
                if table and len(table) > 1:
                    temp_df = pd.DataFrame(table[1:], columns=table[0])
                    all_tables.append(temp_df)

    if len(all_tables) == 0:
        return None

    return pd.concat(all_tables, ignore_index=True)


# -------------------------------------------------
# Grade Functions
# -------------------------------------------------

def assign_grade_normal(score, mean, std):
    if std == 0:
        return "B"

    if score >= mean + 1.5 * std:
        return "A"
    elif score >= mean + 1.0 * std:
        return "A-"
    elif score >= mean + 0.5 * std:
        return "B"
    elif score >= mean:
        return "B-"
    elif score >= mean - 0.5 * std:
        return "C"
    elif score >= mean - 1.0 * std:
        return "C-"
    elif score >= mean - 1.5 * std:
        return "D"
    else:
        return "F"


def assign_grade_manual(score, cutoffs):
    for grade, cutoff in cutoffs:
        if score >= cutoff:
            return grade
    return "F"


def detect_outlier(score, mean, std):
    if std == 0:
        return "Normal"

    z = (score - mean) / std

    if z >= 2:
        return "Very High Outlier"
    elif z <= -2:
        return "Very Low Outlier"
    else:
        return "Normal"


# -------------------------------------------------
# File Upload
# -------------------------------------------------

uploaded_file = st.file_uploader(
    "Upload Excel or PDF file",
    type=["xlsx", "pdf"]
)

if uploaded_file is not None:

    if uploaded_file.name.endswith(".xlsx"):
        df = pd.read_excel(uploaded_file)

    elif uploaded_file.name.endswith(".pdf"):
        df = read_pdf(uploaded_file)

        if df is None:
            st.error("No table found in PDF.")
            st.stop()

    st.subheader("Uploaded Data")
    st.dataframe(df)

    # Convert possible marks columns to numeric
    # for col in df.columns:
    #     df[col] = pd.to_numeric(df[col], errors="coerce")

    non_grading_cols, grading_cols = detect_columns(df)

    st.subheader("Detected Columns")

    c1, c2 = st.columns(2)

    with c1:
        st.write("Non-Grading Fields")
        st.write(non_grading_cols)

    with c2:
        st.write("Detected Grading Parameters")
        st.write(grading_cols)

    # -------------------------------------------------
    # Student Identification
    # -------------------------------------------------

    st.sidebar.header("Student Identification")

    student_name_col = st.sidebar.selectbox(
        "Select student name column",
        df.columns
    )

    # -------------------------------------------------
    # Parameter Selection
    # -------------------------------------------------

    st.sidebar.header("Parameter Selection")

    selected_params = st.sidebar.multiselect(
        "Select grading parameters",
        grading_cols,
        default=grading_cols
    )

    if len(selected_params) == 0:
        st.warning("Please select at least one grading parameter.")
        st.stop()

    # -------------------------------------------------
    # Best-of Logic
    # -------------------------------------------------

    st.sidebar.header("Best-of Logic")

    use_best_of = st.sidebar.checkbox("Use Best-of logic")

    best_of_groups = {}

    if use_best_of:
        group_name = st.sidebar.text_input(
            "Group keyword",
            value="quiz"
        )

        group_cols = [
            col for col in selected_params
            if group_name.lower() in str(col).lower()
        ]

        best_n = st.sidebar.number_input(
            "Best N",
            min_value=1,
            max_value=max(1, len(group_cols)),
            value=min(2, max(1, len(group_cols)))
        )

        st.sidebar.write("Detected group columns:")
        st.sidebar.write(group_cols)

        if len(group_cols) > 0:
            best_of_groups[group_name] = {
                "columns": group_cols,
                "best_n": best_n
            }

    # -------------------------------------------------
    # Weight Assignment
    # -------------------------------------------------

    st.sidebar.header("Weightage Assignment")

    weights = {}
    remaining_params = selected_params.copy()

    for group_name, info in best_of_groups.items():
        for col in info["columns"]:
            if col in remaining_params:
                remaining_params.remove(col)

        weights[group_name] = st.sidebar.number_input(
            f"Weight for Best-of {group_name} group (%)",
            min_value=0.0,
            max_value=100.0,
            value=20.0
        )

    default_weight = round(100 / max(1, len(selected_params)), 2)

    for param in remaining_params:
        weights[param] = st.sidebar.number_input(
            f"Weight for {param} (%)",
            min_value=0.0,
            max_value=100.0,
            value=default_weight
        )

    total_weight = sum(weights.values())

    st.sidebar.write(f"Total Weight = {round(total_weight, 2)}%")

    if round(total_weight, 2) != 100.00:
        st.sidebar.error("Total weight must be exactly 100%.")
        st.stop()

    # -------------------------------------------------
    # Team-Based Assessment
    # -------------------------------------------------

    st.sidebar.header("Team-Based Assessment")

    use_team = st.sidebar.checkbox("Use Team ID mapping")

    if use_team:
        team_id_col = st.sidebar.selectbox(
            "Select Team ID column",
            df.columns
        )

        team_based_params = st.sidebar.multiselect(
            "Select team-based parameters",
            selected_params
        )
    else:
        team_id_col = None
        team_based_params = []

    # -------------------------------------------------
    # Final Marks Calculation
    # -------------------------------------------------

    result_df = df.copy()
    result_df["Final Marks"] = 0.0

    contribution_data = {}

    # Best-of calculation
    for group_name, info in best_of_groups.items():
        cols = info["columns"]
        best_n = info["best_n"]
        group_weight = weights[group_name]

        temp_scores = df[cols].apply(pd.to_numeric, errors="coerce").fillna(0)

        best_scores = np.sort(temp_scores.values, axis=1)[:, -best_n:]
        best_average = best_scores.mean(axis=1)

        weighted_score = best_average * group_weight / 100

        result_df[f"{group_name}_best_score"] = best_average
        result_df["Final Marks"] += weighted_score

        contribution_data[group_name] = weighted_score

    # Normal parameter calculation
    for param in remaining_params:
        score = pd.to_numeric(df[param], errors="coerce").fillna(0)

        # Team-based handling
        if use_team and param in team_based_params and team_id_col is not None:
            temp = pd.DataFrame({
                "Team_ID": df[team_id_col],
                "Score": score
            })

            team_avg = temp.groupby("Team_ID")["Score"].transform("mean")
            score = team_avg

        weighted_score = score * weights[param] / 100

        result_df["Final Marks"] += weighted_score
        contribution_data[param] = weighted_score

    # -------------------------------------------------
    # Summary Statistics
    # -------------------------------------------------

    mean = result_df["Final Marks"].mean()
    std = result_df["Final Marks"].std()

    st.subheader("Summary Statistics")

    m1, m2, m3, m4 = st.columns(4)

    m1.metric("Mean", round(mean, 2))
    m2.metric("Standard Deviation", round(std, 2))
    m3.metric("Highest Marks", round(result_df["Final Marks"].max(), 2))
    m4.metric("Lowest Marks", round(result_df["Final Marks"].min(), 2))

    # -------------------------------------------------
    # Grade Mapping
    # -------------------------------------------------

    st.subheader("Grade Mapping")

    grade_mode = st.radio(
        "Choose grading method",
        ["Normal Distribution Based", "Manual Cutoff Based"]
    )

    if grade_mode == "Normal Distribution Based":
        result_df["Grade"] = result_df["Final Marks"].apply(
            lambda x: assign_grade_normal(x, mean, std)
        )

    else:
        st.write("Enter minimum marks for each grade.")

        g1, g2, g3 = st.columns(3)

        with g1:
            a_cut = st.number_input("A cutoff", value=90.0)
            a_minus_cut = st.number_input("A- cutoff", value=85.0)

        with g2:
            b_plus_cut = st.number_input("B+ cutoff", value=80.0)
            b_cut = st.number_input("B cutoff", value=70.0)

        with g3:
            c_cut = st.number_input("C cutoff", value=50.0)
            f_cut = st.number_input("Fail below", value=40.0)

        cutoffs = [
            ("A", a_cut),
            ("A-", a_minus_cut),
            ("B+", b_plus_cut),
            ("B", b_cut),
            ("C", c_cut),
            ("F", f_cut)
        ]

        result_df["Grade"] = result_df["Final Marks"].apply(
            lambda x: assign_grade_manual(x, cutoffs)
        )

    # -------------------------------------------------
    # Outlier and At-Risk Detection
    # -------------------------------------------------

    result_df["Outlier Status"] = result_df["Final Marks"].apply(
        lambda x: detect_outlier(x, mean, std)
    )

    fail_threshold = st.number_input(
        "At-risk threshold marks",
        value=40.0
    )

    result_df["At Risk"] = result_df["Final Marks"].apply(
        lambda x: "Yes" if x < fail_threshold else "No"
    )

    # -------------------------------------------------
    # Final Table with Colors
    # -------------------------------------------------

    st.subheader("Final Grade Sheet")

    def highlight_students(row):
        if row["At Risk"] == "Yes":
            return [f"background-color: {risk_color}"] * len(row)
        else:
            return [f"background-color: {pass_color}"] * len(row)

    st.dataframe(
        result_df.style.apply(highlight_students, axis=1),
        use_container_width=True
    )

    # -------------------------------------------------
    # Visualizations
    # -------------------------------------------------

    st.subheader("Data Visualization")

    # Histogram + bell curve
    fig1, ax1 = plt.subplots()

    ax1.hist(
        result_df["Final Marks"],
        bins=10,
        density=True,
        alpha=0.6,
        color=hist_color
    )

    x = np.linspace(
        result_df["Final Marks"].min(),
        result_df["Final Marks"].max(),
        100
    )

    if std > 0:
        ax1.plot(
            x,
            norm.pdf(x, mean, std),
            color=bell_color,
            linewidth=2
        )

    ax1.set_title("Marks Distribution with Bell Curve")
    ax1.set_xlabel("Final Marks")
    ax1.set_ylabel("Density")

    st.pyplot(fig1)

    # Student bar chart
    fig2, ax2 = plt.subplots(figsize=(12, 5))

    chart_df = result_df.copy()
    chart_df["Final Marks"] = pd.to_numeric(chart_df["Final Marks"], errors="coerce").fillna(0)

    ax2.bar(
       chart_df[student_name_col].astype(str),
       chart_df["Final Marks"],
       color=bar_color
    )

    ax2.set_title("Student-wise Final Marks Bar Chart")
    ax2.set_xlabel("Student")
    ax2.set_ylabel("Final Marks")
    plt.xticks(rotation=90)
    plt.tight_layout()

    st.pyplot(fig2)

    # Contribution table
    contribution_df = pd.DataFrame(contribution_data)
    contribution_df[student_name_col] = result_df[student_name_col]

    st.subheader("Parameter-wise Contribution")
    st.dataframe(contribution_df, use_container_width=True)

    # Average contribution chart
    fig3, ax3 = plt.subplots()

    avg_contribution = contribution_df.drop(
        columns=[student_name_col]
    ).mean()

    ax3.bar(
        avg_contribution.index,
        avg_contribution.values,
        color=bar_color
    )

    ax3.set_title("Average Parameter-wise Contribution")
    ax3.set_xlabel("Parameter")
    ax3.set_ylabel("Average Weighted Marks")
    plt.xticks(rotation=45)

    st.pyplot(fig3)

    # Box plot
    st.subheader("Box Plot for Outlier Detection")

    fig4, ax4 = plt.subplots()

    ax4.boxplot(result_df["Final Marks"])
    ax4.set_title("Box Plot of Final Marks")
    ax4.set_ylabel("Final Marks")

    st.pyplot(fig4)

    # -------------------------------------------------
    # Download Excel Report
    # -------------------------------------------------

    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        result_df.to_excel(
            writer,
            index=False,
            sheet_name="Final Grades"
        )

        contribution_df.to_excel(
            writer,
            index=False,
            sheet_name="Contributions"
        )

        summary_df = pd.DataFrame({
            "Metric": [
                "Mean",
                "Standard Deviation",
                "Highest Marks",
                "Lowest Marks"
            ],
            "Value": [
                mean,
                std,
                result_df["Final Marks"].max(),
                result_df["Final Marks"].min()
            ]
        })

        summary_df.to_excel(
            writer,
            index=False,
            sheet_name="Summary"
        )

    st.download_button(
        label="Download Excel Report",
        data=output.getvalue(),
        file_name="final_grade_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("Please upload an Excel or PDF file to start grading.")