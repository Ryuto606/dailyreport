import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from st_aggrid import AgGrid, GridOptionsBuilder
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import altair as alt

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

# ===== 通所スプレッドシート =====
sheet_url = "https://docs.google.com/spreadsheets/d/1v4rNnnwxUcSN_O2QjZhHowVGyVclrWlYo8w8yRdd89w/edit"
spreadsheet = client.open_by_url(sheet_url)

worksheet_form = spreadsheet.worksheet("フォームの回答 1")
records_form = worksheet_form.get_all_records()
df_form = pd.DataFrame(records_form)

worksheet_map = spreadsheet.worksheet("一覧")
records_map = worksheet_map.get_all_records()
df_map = pd.DataFrame(records_map)

# ===== 退所スプレッドシート =====
sheet_url_exit = "https://docs.google.com/spreadsheets/d/11TMeEch6jzvJBOdjyGYkCRfG6ltWHxM8XK4BZSLCnKM/edit"
spreadsheet_exit = client.open_by_url(sheet_url_exit)

worksheet_exit = spreadsheet_exit.worksheet("Sheet1")
records_exit = worksheet_exit.get_all_records()
df_exit = pd.DataFrame(records_exit)

# ===== 通所前処理 =====
df_form.rename(columns={df_form.columns[0]: "Timestamp", df_form.columns[1]: "Email"}, inplace=True)
df_map.columns = ["Email", "Name"]

df = pd.merge(df_form, df_map, on="Email", how="left")
df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
df["Timestamp_str"] = df["Timestamp"].dt.strftime("%Y-%m-%d %H:%M")
df["Date"] = df["Timestamp"].dt.strftime("%Y-%m-%d")
df["YearMonth"] = df["Timestamp"].dt.strftime("%Y-%m")
df["Weekday"] = df["Timestamp"].dt.day_name()

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

cols = df.columns.tolist()
for col in ["Timestamp_str", "Name", "Email", "Timestamp"]:
    if col in cols:
        cols.remove(col)
df = df[["Timestamp_str", "Name"] + cols + ["Email", "Timestamp"]]

# ===== 退所前処理 =====
df_exit.rename(columns={df_exit.columns[0]: "Timestamp", df_exit.columns[1]: "Email"}, inplace=True)
df_exit = pd.merge(df_exit, df_map, on="Email", how="left")
df_exit["Timestamp"] = pd.to_datetime(df_exit["Timestamp"], errors="coerce")
df_exit["Timestamp_str"] = df_exit["Timestamp"].dt.strftime("%Y-%m-%d %H:%M")
df_exit["Date"] = df_exit["Timestamp"].dt.strftime("%Y-%m-%d")
df_exit["YearMonth"] = df_exit["Timestamp"].dt.strftime("%Y-%m")

cols_exit = df_exit.columns.tolist()
for col in ["Timestamp_str", "Name", "Email", "Timestamp"]:
    if col in cols_exit:
        cols_exit.remove(col)
df_exit = df_exit[["Timestamp_str", "Name"] + cols_exit + ["Email", "Timestamp"]]

# ✅ 通所表示は相談・連絡までに限定
show_cols = [
    "Timestamp_str", "Name", "Date", "Weekday",
    "就寝時間", "起床時間", "睡眠時間", "睡眠の質", "朝食",
    "入浴", "服薬", "体温（℃）",
    "気分（起床時）",
    "オフタイムコントロール [睡眠]",  # これを列名マッピングで「睡眠」にするなら後で対応
    "オフタイムコントロール [食事]",
    "オフタイムコントロール [ストレス]",
    "良好サイン", "注意サイン", "悪化サイン",
    "今日の自分の状態の課題は？", "課題の原因はなんですか？", "課題の対処はどうしますか？",
    "本日の訓練内容および出席講座（箇条書き）",
    "今日の目標",
    "相談・連絡"
]

# show_cols を適切に制御（「相談・連絡」まで必要な場合は手動で順序を調整）

# ===== UI =====
mode = st.radio(
    "表示モードを選択",
    ["📅 日付別（全員）", "👤 利用者別（月別）", "📊 利用者分析"],
    horizontal=True
)

if mode == "📅 日付別（全員）":
    sel_date = st.date_input("表示する日付", value=pd.Timestamp.today().date())

    daily_df = df[df["Date"] == sel_date.strftime("%Y-%m-%d")]
    daily_df = daily_df.sort_values("Timestamp", ascending=True)
    display_df = daily_df[show_cols].drop(columns=["Email", "Timestamp"], errors="ignore")

    st.subheader(f"📅 {sel_date} 【通所日報】（{len(display_df)} 件）")
    gb = GridOptionsBuilder.from_dataframe(display_df)
    gb.configure_default_column(editable=False)
    gb.configure_column("Timestamp_str", header_name="Timestamp", pinned="left")
    gb.configure_column("Name", pinned="left")
    AgGrid(display_df, gridOptions=gb.build(), height=400)

    exit_df = df_exit[df_exit["Date"] == sel_date.strftime("%Y-%m-%d")]
    exit_df = exit_df.sort_values("Timestamp", ascending=True)
    display_exit_df = exit_df.drop(columns=["Timestamp"])

    st.subheader(f"📅 {sel_date} 【退所日報】（{len(display_exit_df)} 件）")
    gb_exit = GridOptionsBuilder.from_dataframe(display_exit_df)
    gb_exit.configure_default_column(editable=False)
    gb_exit.configure_column("Timestamp_str", header_name="Timestamp", pinned="left")
    gb_exit.configure_column("Name", pinned="left")
    AgGrid(display_exit_df, gridOptions=gb_exit.build(), height=400)

elif mode == "👤 利用者別（月別）":
    names = sorted(df["Name"].dropna().unique())
    sel_name = st.selectbox("利用者を選択", names)
    sel_month = st.selectbox("表示する月", sorted(df["YearMonth"].dropna().unique()))

    user_df = df[(df["Name"] == sel_name) & (df["YearMonth"] == sel_month)]
    user_df = user_df.sort_values("Timestamp", ascending=True)
    display_user_df = user_df[show_cols].drop(columns=["Email", "Timestamp"], errors="ignore")

    st.subheader(f"👤 {sel_name} {sel_month} 【通所日報】（{len(user_df)} 件）")
    gb = GridOptionsBuilder.from_dataframe(user_df.drop(columns=["Timestamp"]))
    gb.configure_default_column(editable=False)
    gb.configure_default_column(tooltipField="__colName__", wrapText=True, autoHeight=True, cellStyle={'whiteSpace': 'normal'})
    gb.configure_column("Timestamp_str", header_name="Timestamp", pinned="left")
    gb.configure_column("Name", pinned="left")
    gb.configure_column("オフタイムコントロール [睡眠]", header_name="睡眠")
    gb.configure_column("オフタイムコントロール [食事]", header_name="食事")
    gb.configure_column("オフタイムコントロール [ストレス]", header_name="ストレス")
    AgGrid(user_df.drop(columns=["Timestamp"]), gridOptions=gb.build(), height=400)

    user_exit_df = df_exit[(df_exit["Name"] == sel_name) & (df_exit["YearMonth"] == sel_month)]
    user_exit_df = user_exit_df.sort_values("Timestamp", ascending=True)
    st.subheader(f"👤 {sel_name} {sel_month} 【退所日報】（{len(user_exit_df)} 件）")
    gb_exit = GridOptionsBuilder.from_dataframe(user_exit_df.drop(columns=["Timestamp"]))
    gb_exit.configure_default_column(editable=False)
    gb_exit.configure_default_column(tooltipField="__colName__", wrapText=True, autoHeight=True, cellStyle={'whiteSpace': 'normal'})
    gb_exit.configure_column("Timestamp_str", header_name="Timestamp", pinned="left")
    gb_exit.configure_column("Name", pinned="left")
    AgGrid(user_exit_df.drop(columns=["Timestamp"]), gridOptions=gb_exit.build(), height=400)

else:
    names = sorted(df["Name"].dropna().unique())
    sel_name = st.selectbox("分析対象", names)
    person_df = df[df["Name"] == sel_name].copy()

    st.subheader(f"📊 {sel_name} の分析")

    st.markdown("### 月ごとの通所回数")
    st.bar_chart(person_df.groupby("YearMonth").size())

    st.markdown("### 曜日別の出席傾向")
    heatmap = alt.Chart(
        person_df.groupby(["YearMonth", "Weekday"]).size().reset_index(name="Count")
    ).mark_rect().encode(
        x=alt.X('Weekday:N', sort=["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]),
        y='YearMonth:N',
        color='Count:Q'
    )
    st.altair_chart(heatmap, use_container_width=True)

    st.markdown("### 起床・就寝時間平均とばらつき")
    valid_wakeup = person_df["起床時間_dt"].dropna()
    valid_bed = person_df["就寝時間_dt"].dropna()

    wakeup_sec = valid_wakeup.dt.hour * 3600 + valid_wakeup.dt.minute * 60
    bed_sec = valid_bed.dt.hour * 3600 + valid_bed.dt.minute * 60

    bed_sec_adj = [b+86400 if b < w else b for w, b in zip(wakeup_sec, bed_sec)]

    def sec2hm(s): h, m = divmod(int(s)//60, 60); return f"{h:02}:{m:02}"

    st.metric("平均起床時間", sec2hm(wakeup_sec.mean()))
    st.metric("平均就寝時間", sec2hm(pd.Series(bed_sec_adj).mean()))

    st.markdown("### 睡眠時間の推移")
    st.line_chart(person_df[["Date", "睡眠時間_h"]].dropna().set_index("Date"))

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

    st.markdown("### 📌 相談・連絡")
    st.dataframe(person_df[person_df["相談・連絡"].notna()][["Date","相談・連絡"]])
