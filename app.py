import streamlit as st
import pandas as pd
import io

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(page_title="Production Data Merge App", layout="wide")

st.title("Production Data Merge App 🏭")
st.markdown("Merge production information from FRPMES0131_CCL, Merged_Data, 塗料檢驗報告 and FRLMAM1002.")

st.info(
    "📁 Please upload all 4 required files. File names can be different, "
    "but each file must be uploaded into the correct slot."
)

# ============================================================
# FILE UPLOADERS
# ============================================================
col1, col2, col3, col4 = st.columns(4)

with col1:
    file_ccl = st.file_uploader(
        "1. Base: FRPMES0131_CCL",
        type=["csv", "xlsx", "xls"],
        key="file_ccl",
    )

with col2:
    file_merged = st.file_uploader(
        "2. Lookup: Merged_Data",
        type=["csv", "xlsx", "xls"],
        key="file_merged",
    )

with col3:
    file_report = st.file_uploader(
        "3. Lookup: 塗料檢驗報告",
        type=["csv", "xlsx", "xls"],
        key="file_report",
    )

with col4:
    file_order = st.file_uploader(
        "4. Lookup: FRLMAM1002",
        type=["csv", "xlsx", "xls"],
        key="file_order",
    )


# ============================================================
# HELPERS
# ============================================================
@st.cache_data(show_spinner=False)
def load_and_clean_data(uploaded_file):
    """Read CSV/Excel and normalize column names."""
    file_name = uploaded_file.name.lower()

    if file_name.endswith(".csv"):
        # Try common encodings used in Taiwan/Chinese data exports.
        try:
            df = pd.read_csv(uploaded_file, low_memory=False, encoding="utf-8-sig")
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, low_memory=False, encoding="big5")
    else:
        df = pd.read_excel(uploaded_file)

    df = df.dropna(how="all").copy()
    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.replace("\n", "", regex=False)
        .str.replace("\r", "", regex=False)
    )
    return df


def super_clean_key(series):
    """Normalize lookup keys without changing normal data columns."""
    s = (
        series.astype("string")
        .str.strip()
        .str.upper()
        .str.replace(r"\.0$", "", regex=True)
    )
    return s.replace({"NAN": pd.NA, "NONE": pd.NA, "<NA>": pd.NA, "": pd.NA})


def add_missing_columns(df, required_cols):
    """Ensure requested output columns always exist, even if a source file lacks them."""
    out = df.copy()
    for col in required_cols:
        if col not in out.columns:
            out[col] = pd.NA
    return out


def build_lookup(df, key_col, value_cols, keep="last"):
    """Create a one-row-per-key lookup table to prevent row multiplication."""
    existing = [c for c in [key_col] + value_cols if c in df.columns]
    if key_col not in existing:
        return None

    lookup = df[existing].copy()
    lookup = lookup.dropna(subset=[key_col])
    lookup = lookup.drop_duplicates(subset=[key_col], keep=keep)
    return lookup


def show_missing_columns(source_name, actual_columns, expected_columns):
    missing = [c for c in expected_columns if c not in actual_columns]
    if missing:
        st.warning(
            f"⚠️ {source_name}: missing {len(missing)} requested column(s): "
            + ", ".join(missing)
        )
    return missing


# ============================================================
# REQUIRED COLUMN DEFINITIONS
# ============================================================
# Step 1: columns from FRPMES0131_CCL
# 塗料編號 is also retained because it is the key required by Step 3.
CCL_OUTPUT_COLS = [
    "線別",
    "生產日期",
    "品名代碼",
    "投入鋼捲號碼",
    "產出鋼捲號碼",
    "訂單號碼",
    "塗料編號",
    "正面漆膜厚",
    "正面底漆膜厚",
    "背漆代號",
    "熱軋材質",
    "鍍製別代碼",
    "產品規格代碼",
    "訂單厚度",
    "訂單寬度",
    "處置代號",
]

# Step 2: columns from Merged_Data by 產出鋼捲號碼 = COIL_NO
MERGED_LOOKUP_COLS = [
    "TOP_STANDARD_PLATE",
    "BACK_STANDARD_PLATE",
    "TOPPAINT_BATCH_NO",
    "TTMPAINT_BATCH_NO",
    "BACKPAINT_BATCH_NO",
    "NORTH_TOP_DELTA_E",
    "NORTH_TOP_DELTA_L",
    "NORTH_TOP_DELTA_A",
    "NORTH_TOP_DELTA_B",
    "SOUTH_TOP_DELTA_E",
    "SOUTH_TOP_DELTA_L",
    "SOUTH_TOP_DELTA_A",
    "SOUTH_TOP_DELTA_B",
    "NORTH_TOP_FILM_THICK",
    "SOUTH_TOP_FILM_THICK",
    "NORTH_TOP_BASE_FILM_THICK",
    "SOUTH_TOP_BASE_FILM_THICK",
    "NORTH_BACK_FILM_THICK",
    "SOUTH_BACK_FILM_THICK",
    "NORTH_BACK_BASE_FILM_THICK",
    "SOUTH_BACK_BASE_FILM_THICK",
    "BACKFILM_THICK",
    "NORTH_TOP_BLANCH",
    "SOUTH_TOP_BLANCH",
    "NORTH_BACK_BLANCH",
    "SOUTH_BACK_BLANCH",
]

# Step 3: columns from 塗料檢驗報告 by 塗料編號
PAINT_CODE_LOOKUP_COLS = [
    "光澤60度反射(下限)",
    "光澤60度反射(上限)",
]

# Step 4: columns from 塗料檢驗報告 by TOPPAINT_BATCH_NO = 製造批號
PAINT_BATCH_LOOKUP_COLS = [
    "光澤",
    "容許誤差△E",
    "容許誤差△L",
    "容許誤差△a",
    "容許誤差△b",
]

# Step 5: columns from FRLMAM1002 by 訂單號碼
ORDER_LOOKUP_COLS = [
    "用途碼",
    "用途中文說明",
]

FINAL_OUTPUT_COLS = (
    CCL_OUTPUT_COLS
    + MERGED_LOOKUP_COLS
    + PAINT_CODE_LOOKUP_COLS
    + PAINT_BATCH_LOOKUP_COLS
    + ORDER_LOOKUP_COLS
)


# ============================================================
# MAIN PROCESS
# ============================================================
if file_ccl and file_merged and file_report and file_order:
    st.markdown("---")

    if st.button("🚀 Process & Merge Data", type="primary", use_container_width=True):
        try:
            with st.status("🚀 Data processing pipeline started...", expanded=True) as status:
                # ----------------------------------------------------
                # LOAD DATA
                # ----------------------------------------------------
                st.write("⏳ Reading FRPMES0131_CCL...")
                df_ccl = load_and_clean_data(file_ccl)

                st.write("⏳ Reading Merged_Data...")
                df_merged = load_and_clean_data(file_merged)

                st.write("⏳ Reading 塗料檢驗報告...")
                df_report = load_and_clean_data(file_report)

                st.write("⏳ Reading FRLMAM1002...")
                df_order = load_and_clean_data(file_order)

                # ----------------------------------------------------
                # STEP 1 - BASE: FRPMES0131_CCL
                # ----------------------------------------------------
                st.write("1️⃣ Building base dataset from FRPMES0131_CCL...")

                # Clean keys used in later steps
                for key_col in ["產出鋼捲號碼", "訂單號碼", "塗料編號", "面漆代號", "背漆代號"]:
                    if key_col in df_ccl.columns:
                        df_ccl[key_col] = super_clean_key(df_ccl[key_col])

                # Fallback only when FRPMES0131_CCL does not contain 塗料編號.
                # This keeps the app usable while clearly preferring the requested source column.
                if "塗料編號" not in df_ccl.columns:
                    if "面漆代號" in df_ccl.columns:
                        df_ccl["塗料編號"] = df_ccl["面漆代號"]
                        st.info("ℹ️ FRPMES0131_CCL has no 塗料編號 column, so 面漆代號 is temporarily used as 塗料編號 for Step 3 lookup.")
                    else:
                        df_ccl["塗料編號"] = pd.NA

                show_missing_columns(
                    "FRPMES0131_CCL",
                    df_ccl.columns,
                    CCL_OUTPUT_COLS,
                )

                df_ccl = add_missing_columns(df_ccl, CCL_OUTPUT_COLS)
                final_df = df_ccl[CCL_OUTPUT_COLS].copy()

                # ----------------------------------------------------
                # STEP 2 - Merged_Data
                # 產出鋼捲號碼 (CCL) = COIL_NO (Merged_Data)
                # ----------------------------------------------------
                st.write("2️⃣ Mapping Merged_Data by 產出鋼捲號碼 ↔ COIL_NO...")

                if "COIL_NO" not in df_merged.columns:
                    raise KeyError("Merged_Data is missing the required key column: COIL_NO")

                df_merged["_MERGE_COIL_KEY"] = super_clean_key(df_merged["COIL_NO"])
                final_df["_MERGE_COIL_KEY"] = super_clean_key(final_df["產出鋼捲號碼"])

                show_missing_columns(
                    "Merged_Data",
                    df_merged.columns,
                    MERGED_LOOKUP_COLS,
                )

                merged_lookup = build_lookup(
                    df_merged,
                    "_MERGE_COIL_KEY",
                    MERGED_LOOKUP_COLS,
                    keep="last",
                )

                if merged_lookup is not None:
                    final_df = final_df.merge(
                        merged_lookup,
                        on="_MERGE_COIL_KEY",
                        how="left",
                        validate="m:1",
                    )

                final_df = add_missing_columns(final_df, MERGED_LOOKUP_COLS)

                # ----------------------------------------------------
                # STEP 3 - 塗料檢驗報告 by 塗料編號
                # ----------------------------------------------------
                st.write("3️⃣ Mapping 塗料檢驗報告 by 塗料編號...")

                if "塗料編號" not in df_report.columns:
                    raise KeyError("塗料檢驗報告 is missing the required key column: 塗料編號")

                df_report["_PAINT_CODE_KEY"] = super_clean_key(df_report["塗料編號"])
                final_df["_PAINT_CODE_KEY"] = super_clean_key(final_df["塗料編號"])

                show_missing_columns(
                    "塗料檢驗報告 / 塗料編號 lookup",
                    df_report.columns,
                    PAINT_CODE_LOOKUP_COLS,
                )

                paint_code_lookup = build_lookup(
                    df_report,
                    "_PAINT_CODE_KEY",
                    PAINT_CODE_LOOKUP_COLS,
                    keep="last",
                )

                if paint_code_lookup is not None:
                    final_df = final_df.merge(
                        paint_code_lookup,
                        on="_PAINT_CODE_KEY",
                        how="left",
                        validate="m:1",
                    )

                final_df = add_missing_columns(final_df, PAINT_CODE_LOOKUP_COLS)

                # ----------------------------------------------------
                # STEP 4 - 塗料檢驗報告 by batch
                # TOPPAINT_BATCH_NO (Merged_Data) = 製造批號 (塗料檢驗報告)
                # ----------------------------------------------------
                st.write("4️⃣ Mapping 塗料檢驗報告 by TOPPAINT_BATCH_NO ↔ 製造批號...")

                if "製造批號" not in df_report.columns:
                    raise KeyError("塗料檢驗報告 is missing the required key column: 製造批號")

                df_report["_PAINT_BATCH_KEY"] = super_clean_key(df_report["製造批號"])
                final_df["_PAINT_BATCH_KEY"] = super_clean_key(final_df["TOPPAINT_BATCH_NO"])

                show_missing_columns(
                    "塗料檢驗報告 / 製造批號 lookup",
                    df_report.columns,
                    PAINT_BATCH_LOOKUP_COLS,
                )

                paint_batch_lookup = build_lookup(
                    df_report,
                    "_PAINT_BATCH_KEY",
                    PAINT_BATCH_LOOKUP_COLS,
                    keep="last",
                )

                if paint_batch_lookup is not None:
                    final_df = final_df.merge(
                        paint_batch_lookup,
                        on="_PAINT_BATCH_KEY",
                        how="left",
                        validate="m:1",
                    )

                final_df = add_missing_columns(final_df, PAINT_BATCH_LOOKUP_COLS)

                # ----------------------------------------------------
                # STEP 5 - FRLMAM1002
                # 訂單號碼 (CCL) = 訂單號碼 (FRLMAM1002)
                # ----------------------------------------------------
                st.write("5️⃣ Mapping FRLMAM1002 by 訂單號碼...")

                if "訂單號碼" not in df_order.columns:
                    raise KeyError("FRLMAM1002 is missing the required key column: 訂單號碼")

                df_order["_ORDER_KEY"] = super_clean_key(df_order["訂單號碼"])
                final_df["_ORDER_KEY"] = super_clean_key(final_df["訂單號碼"])

                show_missing_columns(
                    "FRLMAM1002",
                    df_order.columns,
                    ORDER_LOOKUP_COLS,
                )

                order_lookup = build_lookup(
                    df_order,
                    "_ORDER_KEY",
                    ORDER_LOOKUP_COLS,
                    keep="last",
                )

                if order_lookup is not None:
                    final_df = final_df.merge(
                        order_lookup,
                        on="_ORDER_KEY",
                        how="left",
                        validate="m:1",
                    )

                final_df = add_missing_columns(final_df, ORDER_LOOKUP_COLS)

                # ----------------------------------------------------
                # FINAL OUTPUT
                # ----------------------------------------------------
                st.write("🧹 Arranging final output columns...")

                final_df = add_missing_columns(final_df, FINAL_OUTPUT_COLS)
                output_df = final_df[FINAL_OUTPUT_COLS].copy()

                # Excel-friendly date display without forcing invalid dates to NaT.
                if "生產日期" in output_df.columns:
                    parsed_date = pd.to_datetime(output_df["生產日期"], errors="coerce")
                    valid_date_mask = parsed_date.notna()
                    output_df.loc[valid_date_mask, "生產日期"] = parsed_date.loc[valid_date_mask].dt.strftime("%Y-%m-%d")

                status.update(
                    label="✅ Data merged successfully!",
                    state="complete",
                    expanded=False,
                )

            # ========================================================
            # RESULT SUMMARY
            # ========================================================
            st.success(f"✅ Merge completed. Total output rows: {len(output_df):,}")
            st.write("👀 **Data Preview:**")
            st.dataframe(output_df.head(20), use_container_width=True)

            # ========================================================
            # EXCEL EXPORT
            # ========================================================
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                output_df.to_excel(writer, index=False, sheet_name="Production Data")

                ws = writer.book["Production Data"]
                ws.freeze_panes = "A2"
                ws.auto_filter.ref = ws.dimensions

                # Basic width adjustment for readability
                for column_cells in ws.columns:
                    max_length = 0
                    column_letter = column_cells[0].column_letter
                    for cell in column_cells[:200]:
                        value = "" if cell.value is None else str(cell.value)
                        max_length = max(max_length, len(value))
                    ws.column_dimensions[column_letter].width = min(max(max_length + 2, 12), 28)

            output.seek(0)

            st.download_button(
                label="📥 Download Production Data Merge App.xlsx",
                data=output,
                file_name="Production Data Merge App.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        except Exception as e:
            st.error(f"❌ Processing failed: {e}")
            st.exception(e)

else:
    st.warning("⚠️ Please upload all 4 files to proceed.")
