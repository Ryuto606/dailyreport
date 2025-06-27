import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from st_aggrid import AgGrid, GridOptionsBuilder


# ===== ページ設定 =====
st.set_page_config(page_title="通所日報ダッシュボード", layout="wide")
st.title("📝 通所日報ダッシュボード")

# ===== Google 認証 =====
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Streamlit Cloud の secrets から認証情報を取得
credentials = Credentials.from_service_account_info(
    st.secrets["connections"]["gsheets"],
    scopes=scope
)

client = gspread.authorize(credentials)

# ===== スプレッドシートを開く =====
sheet_url = "https://docs.google.com/spreadsheets/d/1v4rNnnwxUcSN_O2QjZhHowVGyVclrWlYo8w8yRdd89w/edit"
spreadsheet = client.open_by_url(sheet_url)

# ===== シート読み込み =====
# ① フォーム回答シート
worksheet_form = spreadsheet.worksheet("フォームの回答 1")
records_form = worksheet_form.get_all_records()
df_form = pd.DataFrame(records_form)

# ② メールアドレス ⇨ 氏名対応表シート
worksheet_map = spreadsheet.worksheet("一覧")
records_map = worksheet_map.get_all_records()
df_map = pd.DataFrame(records_map)

# ===== データ前処理 =====
# カラム整理
df_form.rename(columns={
    df_form.columns[0]: "Timestamp",
    df_form.columns[1]: "Email",
}, inplace=True)

df_map.columns = ["Email", "Name"]

# JOIN
df = pd.merge(df_form, df_map, on="Email", how="left")

# === 日付列 & 表示用列 ===
df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
df["Timestamp_str"] = df["Timestamp"].dt.strftime("%Y-%m-%d %H:%M")
df["Date"] = df["Timestamp"].dt.strftime("%Y-%m-%d")
df["YearMonth"] = df["Timestamp"].dt.strftime("%Y-%m")

# === 不要な列を削除
columns_to_hide = ["名"]
df = df.drop(columns=[col for col in columns_to_hide if col in df.columns])

# === 「名前」を Timestamp の次に移動
# まず今のカラム順を取得
cols = df.columns.tolist()

# === 列順: Timestamp_str → Name → 他 → Email ===
cols = df.columns.tolist()
for col in ["Timestamp_str", "Name", "Email", "Timestamp"]:
    if col in cols:
        cols.remove(col)
new_order = ["Timestamp_str", "Name"] + cols + ["Email", "Timestamp"]
df = df[new_order]

# ===== UI =====
# ===== UI =====
mode = st.radio("表示モードを選択", ["📅 日付別（全員）", "👤 利用者別（月別）"], horizontal=True)

if mode == "📅 日付別（全員）":
    sel_date = st.date_input("表示する日付", value=pd.Timestamp.today().date())

    daily_df = df[df["Date"] == sel_date.strftime("%Y-%m-%d")]
    daily_df = daily_df.sort_values("Timestamp", ascending=True)

    # 表示用: Timestamp は除外
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

else:
    names = sorted(df["Name"].dropna().unique())
    sel_name = st.selectbox("利用者を選択", names)

    sel_month = st.selectbox(
        "表示する月",
        sorted(df["YearMonth"].dropna().unique())
    )

    user_df = df[(df["Name"] == sel_name) & (df["YearMonth"] == sel_month)]
    user_df = user_df.sort_values("Timestamp", ascending=True)

    # 表示用: Timestamp は除外
    display_user_df = user_df.drop(columns=["Timestamp"])

    st.subheader(f"👤 {sel_name} の {sel_month} の日報（{len(display_user_df)} 件）")

    gb = GridOptionsBuilder.from_dataframe(display_user_df)
    gb.configure_default_column(editable=False)
    gb.configure_column("Timestamp_str", header_name="Timestamp", pinned="left")
    gb.configure_column("Name", pinned="left")
    gridOptions = gb.build()

    AgGrid(
        display_user_df,
        gridOptions=gridOptions,
        height=600,
        enable_enterprise_modules=True,
    )