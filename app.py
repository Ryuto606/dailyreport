import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from st_aggrid import AgGrid, GridOptionsBuilder
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import altair as alt
import pytz
from datetime import datetime

# ===== ページ設定 =====
st.set_page_config(page_title="通所・退所日報ダッシュボード", layout="wide")
st.title("📝 通所・退所日報ダッシュボード")

# ===== Google 認証 =====
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(
    st.secrets["connections"]["gsheets"],
    scopes=scope
)
client = gspread.authorize(credentials)

# ===== スプレッドシート読み込み =====

sheet_url = "https://docs.google.com/spreadsheets/d/1v4rNnnwxUcSN_O2QjZhHowVGyVclrWlYo8w8yRdd89w/edit"
sheet_url_exit = "https://docs.google.com/spreadsheets/d/11TMeEch6jzvJBOdjyGYkCRfG6ltWHxM8XK4BZSLCnKM/edit"
sheet_url_attendance = "https://docs.google.com/spreadsheets/d/1rYV8BsSpyuuBT_KVZR-f0MKbMWQi65lddDQEe_eImuk/edit"

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from st_aggrid import AgGrid, GridOptionsBuilder
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import altair as alt
import pytz
from datetime import datetime
import re

# ===== ページ設定 =====
st.set_page_config(page_title="通所・退所・出席分析ダッシュボード", layout="wide")
st.title("📝 通所・退所・正規化 出席率ダッシュボード")

# ===== Google 認証 =====
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(
    st.secrets["connections"]["gsheets"],
    scopes=scope
)
client = gspread.authorize(credentials)

# ===== スプレッドシート読み込み =====
sheet_url = "https://docs.google.com/spreadsheets/d/1v4rNnnwxUcSN_O2QjZhHowVGyVclrWlYo8w8yRdd89w/edit"
sheet_url_exit = "https://docs.google.com/spreadsheets/d/11TMeEch6jzvJBOdjyGYkCRfG6ltWHxM8XK4BZSLCnKM/edit"
sheet_url_attendance = "https://docs.google.com/spreadsheets/d/1rYV8BsSpyuuBT_KVZR-f0MKbMWQi65lddDQEe_eImuk/edit"

spreadsheet = client.open_by_url(sheet_url)
spreadsheet_exit = client.open_by_url(sheet_url_exit)
spreadsheet_attendance = client.open_by_url(sheet_url_attendance)

# === 正規化シート読み込み ===
@st.cache_data(ttl=600)
def load_attendance():
    return pd.DataFrame(spreadsheet_attendance.worksheet("正規化").get_all_records())

df_attendance = load_attendance()
df_attendance.columns = df_attendance.columns.str.strip()  # 列名空白除去
df_attendance['日付'] = pd.to_datetime(df_attendance['日付'], errors='coerce')
df_attendance['YearMonth'] = df_attendance['日付'].dt.strftime('%Y-%m')

# === フォーム回答
@st.cache_data(ttl=10)
def load_form():
    return pd.DataFrame(spreadsheet.worksheet("フォームの回答 1").get_all_records())

# === 一覧マスター
@st.cache_data(ttl=600)
def load_map():
    return pd.DataFrame(spreadsheet.worksheet("一覧").get_all_records())

# === 退所日報
@st.cache_data(ttl=10)
def load_exit():
    return pd.DataFrame(spreadsheet_exit.worksheet("Sheet1").get_all_records())

df_form = load_form()
df_map  = load_map()
df_exit = load_exit()

# === 通所データ前処理
df_form.rename(columns={df_form.columns[0]: "Timestamp", df_form.columns[1]: "Email"}, inplace=True)
df_map.columns = ["Email", "Name"]
df = pd.merge(df_form, df_map, on="Email", how="left")
df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
df["Timestamp_str"] = df["Timestamp"].dt.strftime("%Y-%m-%d %H:%M")
df["Date"] = df["Timestamp"].dt.strftime("%Y-%m-%d")
df["YearMonth"] = df["Timestamp"].dt.strftime("%Y-%m")

def parse_time(val):
    try:
        if isinstance(val, str):
            return pd.to_datetime(val, format="%H:%M:%S", errors="coerce")
        elif isinstance(val, (int, float)):
            return pd.to_datetime("1899-12-30") + pd.to_timedelta(val, unit="D")
        else:
            return pd.NaT
    except:
        return pd.NaT

df["起床時間_dt"] = df["起床時間"].apply(parse_time)
df["就寝時間_dt"] = df["就寝時間"].apply(parse_time)
df["睡眠時間_h"] = (df["起床時間_dt"] - df["就寝時間_dt"]).dt.total_seconds() / 3600
df.loc[df["睡眠時間_h"] < 0, "睡眠時間_h"] += 24

# === 退所前処理
df_exit.rename(columns={df_exit.columns[0]: "Timestamp", df_exit.columns[1]: "Email"}, inplace=True)
df_exit = pd.merge(df_exit, df_map, on="Email", how="left")
df_exit["Timestamp"] = pd.to_datetime(df_exit["Timestamp"], errors="coerce")
df_exit["Timestamp_str"] = df_exit["Timestamp"].dt.strftime("%Y-%m-%d %H:%M")
df_exit["Date"] = df_exit["Timestamp"].dt.strftime("%Y-%m-%d")
df_exit["YearMonth"] = df_exit["Timestamp"].dt.strftime("%Y-%m")

# === 表示列
show_cols = [
    "Timestamp_str", "Name", "曜日", "就寝時間", "起床時間", "睡眠時間",
    "睡眠の質", "朝食", "入浴", "服薬", "体温（℃）", "気分（起床時）",
    "オフタイムコントロール [睡眠]", "オフタイムコントロール [食事]", "オフタイムコントロール [ストレス]",
    "良好サイン", "注意サイン", "悪化サイン",
    "今日の自分の状態の課題は？", "課題の原因はなんですか？", "課題の対処はどうしますか？",
    "本日の訓練内容および出席講座（箇条書き）", "今日の目標", "相談・連絡"
]

header_map = {
    "Timestamp_str": "Timestamp",
    "Name": "名前",
    "曜日": "曜日",
    "オフタイムコントロール [睡眠]": "睡眠",
    "オフタイムコントロール [食事]": "食事",
    "オフタイムコントロール [ストレス]": "ストレス",
}

# === モード切替
mode = st.radio(
    "表示モードを選択",
    ["📅 日付別（全員）", "👤 利用者別（月別）", "📊 利用者分析"],
    horizontal=True
)

# === 日付別（全員）
if mode == "📅 日付別（全員）":
    japan = pytz.timezone("Asia/Tokyo")
    today_jst = datetime.now(japan).date()

    sel_date = st.date_input("表示する日付", value=today_jst)

    daily_df = df[df["Date"] == sel_date.strftime("%Y-%m-%d")].sort_values("Timestamp")
    display_df = daily_df[[c for c in show_cols if c in daily_df.columns]]
    st.subheader(f"📅 {sel_date} 【通所日報】（{len(display_df)} 件）")
    gb = GridOptionsBuilder.from_dataframe(display_df)
    gb.configure_default_column(wrapText=True, autoHeight=True)
    gb.configure_column("Timestamp_str", header_name="Timestamp", pinned="left")
    gb.configure_column("Name", header_name="名前", pinned="left")
    AgGrid(display_df, gridOptions=gb.build(), height=600)

    exit_df = df_exit[df_exit["Date"] == sel_date.strftime("%Y-%m-%d")].sort_values("Timestamp")
    display_exit_df = exit_df.drop(columns=["Timestamp", "Email", "Date", "YearMonth"], errors="ignore")
    st.subheader(f"📅 {sel_date} 【退所日報】（{len(display_exit_df)} 件）")
    gb_exit = GridOptionsBuilder.from_dataframe(display_exit_df)
    gb_exit.configure_default_column(wrapText=True, autoHeight=True)
    gb_exit.configure_column("Timestamp_str", header_name="Timestamp", pinned="left")
    gb_exit.configure_column("Name", header_name="名前", pinned="left")
    AgGrid(display_exit_df, gridOptions=gb_exit.build(), height=600)

# === 利用者別（月別）
elif mode == "👤 利用者別（月別）":
    names = sorted(df["Name"].dropna().unique())
    sel_name = st.selectbox("利用者を選択", names)
    japan = pytz.timezone("Asia/Tokyo")
    now_month = datetime.now(japan).strftime("%Y-%m")
    months = sorted(df["YearMonth"].dropna().unique())
    month_idx = months.index(now_month) if now_month in months else 0
    sel_month = st.selectbox("表示する月", months, index=month_idx)

    user_df = df[(df["Name"] == sel_name) & (df["YearMonth"] == sel_month)].sort_values("Timestamp")
    display_user_df = user_df[[c for c in show_cols if c in user_df.columns and c != "Date"]]
    user_cols = display_user_df.columns.tolist()
    user_cols = [c for c in user_cols if c not in ["Timestamp_str", "Name"]]
    display_user_df = display_user_df[["Timestamp_str", "Name"] + user_cols]
    st.subheader(f"👤 {sel_name} さん {sel_month} 【通所日報】（{len(display_user_df)} 件）")
    gb = GridOptionsBuilder.from_dataframe(display_user_df)
    gb.configure_default_column(wrapText=True, autoHeight=True)
    gb.configure_column("Timestamp_str", header_name="Timestamp", pinned="left")
    gb.configure_column("Name", header_name="名前", pinned="left")
    AgGrid(display_user_df, gridOptions=gb.build(), height=600)

# === 利用者分析
else:
    names = sorted(df_attendance['氏名'].dropna().unique())
    sel_name = st.selectbox("分析対象", names)
    person_att = df_attendance[df_attendance['氏名'] == sel_name]

    present_count = person_att[person_att['出席状況'] == '出席'].shape[0]
    absent_count = person_att[person_att['出席状況'] == '欠席'].shape[0]
    total_days = present_count + absent_count
    attendance_rate = round((present_count / total_days * 100), 1) if total_days > 0 else 0

    st.subheader(f"✅ {sel_name} の正規化データ出席状況")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("出席日数", f"{present_count} 日")
    col2.metric("欠席日数", f"{absent_count} 日")
    col3.metric("対象日数", f"{total_days} 日")
    col4.metric("出席率", f"{attendance_rate} %")

    st.markdown("### 📅 月別 出席数推移")
    month_summary = (
        person_att.groupby(['YearMonth', '出席状況'])
        .size()
        .reset_index(name='件数')
    )
    chart = alt.Chart(month_summary).mark_bar().encode(
        x=alt.X('YearMonth:N', title='年月'),
        y=alt.Y('件数:Q'),
        color=alt.Color('出席状況:N'),
        tooltip=['YearMonth', '出席状況', '件数']
    ).properties(width=700, height=400)
    st.altair_chart(chart, use_container_width=True)
