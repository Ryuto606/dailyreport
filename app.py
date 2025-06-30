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

spreadsheet = client.open_by_url(sheet_url)
spreadsheet_exit = client.open_by_url(sheet_url_exit)

# ✅ フォーム回答
@st.cache_data(ttl=15)
def load_form():
    return pd.DataFrame(spreadsheet.worksheet("フォームの回答 1").get_all_records())

# ✅ 一覧マスター
@st.cache_data(ttl=600)
def load_map():
    return pd.DataFrame(spreadsheet.worksheet("一覧").get_all_records())

# ✅ 退所日報
@st.cache_data(ttl=15)
def load_exit():
    return pd.DataFrame(spreadsheet_exit.worksheet("Sheet1").get_all_records())

# === 呼び出し ===
df_form = load_form()
df_map  = load_map()
df_exit = load_exit()


# ===== 前処理 =====
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

# ===== 退所前処理 =====
df_exit.rename(columns={df_exit.columns[0]: "Timestamp", df_exit.columns[1]: "Email"}, inplace=True)
df_exit = pd.merge(df_exit, df_map, on="Email", how="left")
df_exit["Timestamp"] = pd.to_datetime(df_exit["Timestamp"], errors="coerce")
df_exit["Timestamp_str"] = df_exit["Timestamp"].dt.strftime("%Y-%m-%d %H:%M")
df_exit["Date"] = df_exit["Timestamp"].dt.strftime("%Y-%m-%d")
df_exit["YearMonth"] = df_exit["Timestamp"].dt.strftime("%Y-%m")

# ===== 表示する列 =====
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

# ===== UI =====
mode = st.radio(
    "表示モードを選択",
    ["📅 日付別（全員）", "👤 利用者別（月別）", "📊 利用者分析"],
    horizontal=True
)

if mode == "📅 日付別（全員）":
    # タイムゾーン付きの「今日」
    japan = pytz.timezone("Asia/Tokyo")
    today_jst = datetime.now(japan).date()

    sel_date = st.date_input(
        "表示する日付",
        value=today_jst
    )

    # ===== 通所日報 =====
    daily_df = df[df["Date"] == sel_date.strftime("%Y-%m-%d")].sort_values("Timestamp")
    display_df = daily_df[[c for c in show_cols if c in daily_df.columns]]

    st.subheader(f"📅 {sel_date} 【通所日報】（{len(display_df)} 件）")
    gb = GridOptionsBuilder.from_dataframe(display_df)
    gb.configure_default_column(
        tooltipField="__colName__",
        wrapText=True,
        autoHeight=True,
        cellStyle={'whiteSpace': 'normal'}
    )
    # ✅ 通所: Timestamp_str と Name を左固定
    gb.configure_column("Timestamp_str", header_name="Timestamp", pinned="left")
    gb.configure_column("Name", header_name="名前", pinned="left")
    for col in display_df.columns:
        if col not in ["Timestamp_str", "Name"]:
            gb.configure_column(col, header_name=header_map.get(col, col))
    AgGrid(display_df, gridOptions=gb.build(), height=600)

    # ===== 退所日報 =====
    exit_df = df_exit[df_exit["Date"] == sel_date.strftime("%Y-%m-%d")].sort_values("Timestamp")
    display_exit_df = exit_df.drop(
        columns=["Timestamp", "Email", "Date", "YearMonth"],
        errors="ignore"
    )

    # ✅ 列順を Timestamp_str → Name → その他 に並べ替え
    exit_cols = display_exit_df.columns.tolist()
    exit_cols = [c for c in exit_cols if c not in ["Timestamp_str", "Name"]]
    exit_cols = ["Timestamp_str", "Name"] + exit_cols
    display_exit_df = display_exit_df[exit_cols]

    st.subheader(f"📅 {sel_date} 【退所日報】（{len(display_exit_df)} 件）")
    gb_exit = GridOptionsBuilder.from_dataframe(display_exit_df)
    gb_exit.configure_default_column(wrapText=True, autoHeight=True)
    gb_exit.configure_column("Timestamp_str", header_name="Timestamp", pinned="left")
    gb_exit.configure_column("Name", header_name="名前", pinned="left")
    AgGrid(display_exit_df, gridOptions=gb_exit.build(), height=600)


elif mode == "👤 利用者別（月別）":
    names = sorted(df["Name"].dropna().unique())
    sel_name = st.selectbox("利用者を選択", names)
    sel_month = st.selectbox("表示する月", sorted(df["YearMonth"].dropna().unique()))

    # ===== 通所日報 =====
    user_df = df[(df["Name"] == sel_name) & (df["YearMonth"] == sel_month)].sort_values("Timestamp")
    display_user_df = user_df[[c for c in show_cols if c in user_df.columns and c != "Date"]]

    # カラム順: Timestamp_str → Name → 残り
    user_cols = display_user_df.columns.tolist()
    user_cols = [c for c in user_cols if c not in ["Timestamp_str", "Name"]]
    display_user_df = display_user_df[["Timestamp_str", "Name"] + user_cols]

    st.subheader(f"👤 {sel_name} さん {sel_month} 【通所日報】（{len(display_user_df)} 件）")
    gb = GridOptionsBuilder.from_dataframe(display_user_df)
    gb.configure_default_column(
        tooltipField="__colName__",
        wrapText=True,
        autoHeight=True,
        cellStyle={'whiteSpace': 'normal'}
    )
    gb.configure_column("Timestamp_str", header_name="Timestamp", pinned="left")
    gb.configure_column("Name", header_name="名前", pinned="left")
    for col in user_cols:
        gb.configure_column(col, header_name=header_map.get(col, col))
    AgGrid(display_user_df, gridOptions=gb.build(), height=600)

    # ===== 退所日報 =====
    user_exit_df = df_exit[(df_exit["Name"] == sel_name) & (df_exit["YearMonth"] == sel_month)].sort_values("Timestamp")
    display_exit_df = user_exit_df.drop(
        columns=["Timestamp", "Email", "Date", "YearMonth"],
        errors="ignore"
    )

    # カラム順: Timestamp_str → Name → 残り
    exit_cols = display_exit_df.columns.tolist()
    exit_cols = [c for c in exit_cols if c not in ["Timestamp_str", "Name"]]
    display_exit_df = display_exit_df[["Timestamp_str", "Name"] + exit_cols]

    st.subheader(f"👤 {sel_name} {sel_month} 【退所日報】（{len(display_exit_df)} 件）")
    gb_exit = GridOptionsBuilder.from_dataframe(display_exit_df)
    gb_exit.configure_default_column(wrapText=True, autoHeight=True)
    gb_exit.configure_column("Timestamp_str", header_name="Timestamp", pinned="left")
    gb_exit.configure_column("Name", header_name="名前", pinned="left")
    AgGrid(display_exit_df, gridOptions=gb_exit.build(), height=600)

else:
    names = sorted(df["Name"].dropna().unique())
    sel_name = st.selectbox("分析対象", names)
    person_df = df[df["Name"] == sel_name].copy()

    st.subheader(f"📊 {sel_name} の分析")

    st.markdown("### 月ごとの通所回数")
    st.bar_chart(person_df.groupby("YearMonth").size())

    st.markdown("### 起床・就寝時間 平均とばらつき")
    valid_wakeup = person_df["起床時間_dt"].dropna()
    wakeup_sec = valid_wakeup.dt.hour * 3600 + valid_wakeup.dt.minute * 60

    valid_bed = person_df["就寝時間_dt"].dropna()
    bed_sec = valid_bed.dt.hour * 3600 + valid_bed.dt.minute * 60

    # 補正
    bed_sec_adjusted = []
    for w, b in zip(wakeup_sec, bed_sec):
        if b > w:
            bed_sec_adjusted.append(b)
        else:
            bed_sec_adjusted.append(b + 86400)
    bed_sec = pd.Series(bed_sec_adjusted)

    def sec2hm(s):
        s = s % 86400
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        return f"{h:02}:{m:02}"

    st.metric("平均起床時間", sec2hm(wakeup_sec.mean()))
    st.metric("起床時間のばらつき (分)", f"{wakeup_sec.std()/60:.1f}")

    st.metric("平均就寝時間", sec2hm(bed_sec.mean()))
    st.metric("就寝時間のばらつき (分)", f"{bed_sec.std()/60:.1f}")

    # === 📌 相談・連絡 ===
    st.markdown("### 📌 相談・連絡（通所）")
    contact_df = person_df[
        person_df["相談・連絡"].notna() & (person_df["相談・連絡"].str.strip() != "なし")
    ]
    st.dataframe(contact_df[["Date", "相談・連絡"]])

    st.markdown("### 🗂 その他（退所）")
    contact_exit_df = df_exit[
        (df_exit["Name"] == sel_name) &
        df_exit["その他"].notna() & (df_exit["その他"].str.strip() != "なし")
    ]
    st.dataframe(contact_exit_df[["Date", "その他"]])

    st.markdown("### 目標・課題 WordCloud")
    texts = (
        person_df["今日の目標"].dropna().tolist()
        + person_df["課題の対処はどうしますか？"].dropna().tolist()
    )
    texts = [t for t in texts if str(t).strip() and str(t).strip() != "なし"]
    text_all = " ".join(texts)
    if text_all.strip():
        wc = WordCloud(
            background_color="white",
            font_path="./fonts/NotoSansJP-Regular.ttf",
            width=800,
            height=400
        ).generate(text_all)
        fig, ax = plt.subplots()
        ax.imshow(wc, interpolation="bilinear")
        ax.axis("off")
        st.pyplot(fig)
    else:
        st.info("テキストが不足しています（すべて『なし』か空です）。")