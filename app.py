import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from st_aggrid import AgGrid, GridOptionsBuilder
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import altair as alt

# ===== ページ設定 =====
st.set_page_config(page_title="通所日報ダッシュボード", layout="wide")
st.title("📝 通所日報ダッシュボード（最新フル版）")

# ===== Google 認証 =====
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

credentials = Credentials.from_service_account_info(
    st.secrets["connections"]["gsheets"],
    scopes=scope
)

client = gspread.authorize(credentials)

# ===== スプレッドシートを開く =====
sheet_url = "https://docs.google.com/spreadsheets/d/1v4rNnnwxUcSN_O2QjZhHowVGyVclrWlYo8w8yRdd89w/edit"
spreadsheet = client.open_by_url(sheet_url)

# ===== シート読み込み =====
worksheet_form = spreadsheet.worksheet("フォームの回答 1")
records_form = worksheet_form.get_all_records()
df_form = pd.DataFrame(records_form)

worksheet_map = spreadsheet.worksheet("一覧")
records_map = worksheet_map.get_all_records()
df_map = pd.DataFrame(records_map)

# ===== データ前処理 =====
df_form.rename(columns={
    df_form.columns[0]: "Timestamp",
    df_form.columns[1]: "Email",
}, inplace=True)

df_map.columns = ["Email", "Name"]

df = pd.merge(df_form, df_map, on="Email", how="left")

df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
df["Timestamp_str"] = df["Timestamp"].dt.strftime("%Y-%m-%d %H:%M")
df["Date"] = df["Timestamp"].dt.strftime("%Y-%m-%d")
df["YearMonth"] = df["Timestamp"].dt.strftime("%Y-%m")
df["Weekday"] = df["Timestamp"].dt.day_name()

# ✅ 起床・就寝時間を シリアル値 or 文字列 両対応でパース
def parse_time(val):
    try:
        if isinstance(val, str):
            return pd.to_datetime(val, format="%H:%M", errors="coerce")
        elif isinstance(val, (int, float)):
            return pd.to_datetime("1899-12-30") + pd.to_timedelta(val, unit="D")
        else:
            return pd.NaT
    except:
        return pd.NaT

df["起床時間_dt"] = df["起床時間"].apply(parse_time)
df["就寝時間_dt"] = df["就寝時間"].apply(parse_time)

# ✅ 睡眠時間（時間単位）
df["睡眠時間_h"] = (df["起床時間_dt"] - df["就寝時間_dt"]).dt.total_seconds() / 3600
df.loc[df["睡眠時間_h"] < 0, "睡眠時間_h"] += 24

# === 不要列を削除
columns_to_hide = ["名"]
df = df.drop(columns=[col for col in columns_to_hide if col in df.columns])

# === 列順: Timestamp_str → Name → 他 → Email
cols = df.columns.tolist()
for col in ["Timestamp_str", "Name", "Email", "Timestamp"]:
    if col in cols:
        cols.remove(col)
new_order = ["Timestamp_str", "Name"] + cols + ["Email", "Timestamp"]
df = df[new_order]

# ===== UI =====
mode = st.radio(
    "表示モードを選択",
    ["📅 日付別（全員）", "👤 利用者別（月別）", "📊 人ごと分析"],
    horizontal=True
)

if mode == "📅 日付別（全員）":
    sel_date = st.date_input("表示する日付", value=pd.Timestamp.today().date())
    daily_df = df[df["Date"] == sel_date.strftime("%Y-%m-%d")]
    daily_df = daily_df.sort_values("Timestamp", ascending=True)
    display_df = daily_df.drop(columns=["Timestamp"])

    st.subheader(f"📅 {sel_date} の日報（{len(display_df)} 件）")

    gb = GridOptionsBuilder.from_dataframe(display_df)
    gb.configure_default_column(editable=False)
    gb.configure_column("Timestamp_str", header_name="Timestamp", pinned="left")
    gb.configure_column("Name", pinned="left")
    gridOptions = gb.build()

    AgGrid(
        display_df,
        gridOptions=gridOptions,
        height=600,
        enable_enterprise_modules=True,
    )

elif mode == "👤 利用者別（月別）":
    names = sorted(df["Name"].dropna().unique())
    sel_name = st.selectbox("利用者を選択", names)
    sel_month = st.selectbox(
        "表示する月",
        sorted(df["YearMonth"].dropna().unique())
    )

    user_df = df[(df["Name"] == sel_name) & (df["YearMonth"] == sel_month)]
    user_df = user_
