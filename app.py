import streamlit as st
import pdfplumber
import pandas as pd
import re

class UniversalFinancialStreamer:
    def __init__(self, x_tolerance=20, y_tolerance=11, mask_numbers=False):
        self.x_tolerance = x_tolerance
        self.y_tolerance = y_tolerance
        self.mask_numbers = mask_numbers  # 数値を隠すかどうかのフラグ
        # 全ページ通してのIDカウンター
        self.row_counter = 0
        self.val_counter = 0

    def process_pdf(self, pdf_file):
        self.row_counter = 0  # 処理開始時にリセット
        self.val_counter = 0
        full_output = []
        with pdfplumber.open(pdf_file) as pdf:
            for i, page in enumerate(pdf.pages):
                words = page.extract_words(
                    x_tolerance=3, 
                    y_tolerance=3, 
                    keep_blank_chars=False
                )
                if not words:
                    continue

                page_stream, baselines = self._generate_page_stream(words)
                
                # StreamlitのUI側に情報を付与
                header = f"=== PAGE {i+1} [Detected {len(baselines)} Columns] ==="
                full_output.append(f"{header}\n{page_stream}")
        return "\n\n".join(full_output)

    def _generate_page_stream(self, words):
        # 1. Y軸（行）でグルーピング
        rows = []
        words.sort(key=lambda w: (w['top'], w['x0']))
        
        current_row = []
        last_y = words[0]['top']
        for w in words:
            if abs(w['top'] - last_y) <= self.y_tolerance:
                current_row.append(w)
            else:
                rows.append(sorted(current_row, key=lambda x: x['x0']))
                current_row = [w]
                last_y = w['top']
        rows.append(current_row)

        # 2. X軸の基準線（列）を動的に特定
        all_x_starts = [w['x0'] for row in rows for w in row]
        col_baselines = self._cluster_coordinates(all_x_starts)

        # 3. ストリーム形式に変換
        lines = []
        for row in rows:
            if not row: continue
            
            self.row_counter += 1
            row_id = f"[r_{self.row_counter:03d}]"
            base_x = int(row[0]['x0'])
            row_str = f"{row_id}<x:{base_x:03d}> "
            
            for w in row:
                text = self._normalize_text(w['text'])
                col_idx = self._get_col_index(w['x0'], col_baselines)
                
                # 数値かどうか判定してIDを振る（ここでマスキング判定）
                tagged_text = self._apply_value_id(text)
                
                row_str += f"<col:{col_idx}, x:{int(w['x0']):03d}> {tagged_text} "
            lines.append(row_str)

        return "\n".join(lines), col_baselines

    def _apply_value_id(self, text):
        """数値データ（整数・小数・負数）にIDを付与、またはマスキングする"""
        clean_val = text.strip()
        
        # 正規表現で数値判定
        if re.fullmatch(r'-?\d+(\.\d+)?', clean_val):
            self.val_counter += 1
            v_id = f"v_{self.val_counter:03d}"
            
            # --- ここで切り替え ---
            if self.mask_numbers:
                return f"<{v_id}:NUMERIC>"
            else:
                return f"<{v_id}:{clean_val}>"
        
        return clean_val

    def _cluster_coordinates(self, coords):
        if not coords: return []
        coords.sort()
        clusters = [coords[0]]
        for c in coords[1:]:
            if c > clusters[-1] + self.x_tolerance:
                clusters.append(c)
        return clusters

    def _get_col_index(self, x, baselines):
        for i, b in enumerate(baselines):
            if abs(x - b) <= self.x_tolerance:
                return i + 1
        return 1

    def _normalize_text(self, text):
        t = text.replace('△', '-').replace('▲', '-').replace(',', '')
        if re.fullmatch(r'\(\d+\.?\d*\)', t):
            t = '-' + t[1:-1]
        return t

# --- Streamlit UI ---
st.set_page_config(page_title="Financial Col-Tagging Tester", layout="wide")

st.title("📑 Dynamic Col-Tagging Tester")
st.markdown("""
このツールは、PDF内のテキスト座標をスキャンし、**列構造を自動特定**します。
サイドバーの「数値をマスキングする」をオンにすると、機密性の高い数値を隠して構造のみを出力できます。
""")

# サイドバーの設定
st.sidebar.header("Tuning Parameters")
x_tol = st.sidebar.slider("X Tolerance (列の結合感度)", 1, 100, 20, help="この範囲内のx座標は同じ列として扱われます。")
y_tol = st.sidebar.slider("Y Tolerance (行の結合感度)", 1, 20, 11, help="この範囲内のy座標は同じ行として扱われます。")

# ★ マスキング切り替えスイッチの追加
mask_on = st.sidebar.checkbox(
    "数値をマスキングする", 
    value=False, 
    help="ONにすると数値が <v_ID:NUMERIC> に置き換わります。"
)

uploaded_file = st.file_uploader("決算短信（PDF）をアップロード", type="pdf")

if uploaded_file:
    # クラス初期化時に mask_numbers 引数を渡す
    streamer = UniversalFinancialStreamer(
        x_tolerance=x_tol, 
        y_tolerance=y_tol, 
        mask_numbers=mask_on
    )
    
    with st.spinner("PDFを解析中..."):
        output = streamer.process_pdf(uploaded_file)
    
    st.subheader("分析結果: 幾何学的ストリーム出力")
    st.text_area("AI用入力データ形式", output, height=700)
    
    if "Detected" in output:
        st.sidebar.success("列解析完了")