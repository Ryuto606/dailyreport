import streamlit as st
import pandas as pd
from streamlit_gsheets_connection import GSheetsConnection

st.set_page_config(page_title="通所日報詳細", layout="wide")
st.title("📝 通所日報ダッシュボード（詳細版）")

# ===== Google Sheets接続 =====
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=600)
def load_data():
    sheet_url = "https://docs.google.com/spreadsheets/d/1v4rNnnwxUcSN_O2QjZhHowVGyVclrWlYo8w8yRdd89w/edit?resourcekey=&gid=663617233#gid=663617233"

    # 1️⃣ 回答シート
    df_form = conn.read(
        worksheet="フォームの回答 1",
        url=sheet_url
    )

    df_form.rename(columns={
        df_form.columns[0]: "Timestamp",
        df_form.columns[1]: "Email"
        # 他は元名のままでOK
    }, inplace=True)

    # 2️⃣ 氏名対応表
    df_map = conn.read(
        worksheet="一覧",
        url=sheet_url
    )
    df_map.columns = ["Email", "Name"]

    # 3️⃣ JOIN
    df = pd.merge(df_form, df_map, on="Email", how="left")

    # 4️⃣ 日付/年月
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    df["Date"] = df["Timestamp"].dt.date
    df["YearMonth"] = df["Timestamp"].dt.strftime("%Y-%m")

    # 並べ替え
    df = df.sort_values("Timestamp", ascending=False)

    return df

df = load_data()

# ===== 表示モード =====
mode = st.radio("表示モード", ["📅 日付別（全員）", "👤 利用者別（月別）"], horizontal=True)

if mode == "📅 日付別（全員）":
    sel_date = st.date_input("表示する日付", value=pd.Timestamp.today().date())
    daily_df = df[df["Date"] == sel_date]

    st.subheader(f"📅 {sel_date} の日報（{len(daily_df)}件）")
    st.dataframe(
        daily_df[["Name", "曜日", "起床時間", "睡眠時間", "気分（起床時）",
                  "良好サイン", "注意サイン", "悪化サイン", "相談・連絡", "Timestamp"]],
        use_container_width=True
    )

else:
    sel_user = st.selectbox("利用者を選択", sorted(df["Name"].dropna().unique()))
    months = sorted(df["YearMonth"].unique(), reverse=True)
    sel_month = st.selectbox("月を選択", months)

    user_df = df[(df["Name"] == sel_user) & (df["YearMonth"] == sel_month)]

    st.subheader(f"👤 {sel_user} の {sel_month} の日報（{len(user_df)}件）")

    st.dataframe(
        user_df[["Date", "曜日", "就寝時間", "起床時間", "睡眠時間", "睡眠の質",
                 "朝食", "入浴", "服薬", "体温（℃）　※任意",
                 "気分（起床時）", "オフタイムコントロール [睡眠]", "オフタイムコントロール [食事]",
                 "オフタイムコントロール [ストレス]", "良好サイン", "注意サイン", "悪化サイン",
                 "今日の自分の状態の課題は？", "課題の原因はなんですか？", "課題の対処はどうしますか？",
                 "本日の訓練内容および出席講座（箇条書き）", "今日の目標", "相談・連絡", "Timestamp"]],
        use_container_width=True
    )
