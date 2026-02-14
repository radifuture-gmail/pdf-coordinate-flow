import streamlit as st
import pdfplumber
import pandas as pd

class UniversalFinancialStreamer:
    def __init__(self, x_tolerance=10, y_tolerance=3):
        self.x_tolerance = x_tolerance
        self.y_tolerance = y_tolerance

    def process_pdf(self, pdf_file):
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
                
                # StreamlitのUI側に「特定された列数」を表示するための情報を付与
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

        # 2. X軸の基準線（列）を動的に特定（最重要ロジック）
        all_x_starts = [w['x0'] for row in rows for w in row]
        col_baselines = self._cluster_coordinates(all_x_starts)

        # 3. ストリーム形式に変換（colタグを付与）
        lines = []
        for row in rows:
            if not row: continue
            base_x = int(row[0]['x0'])
            # 行の先頭に基準となるx座標を付与
            row_str = f"<x:{base_x:03d}> "
            
            for w in row:
                text = self._normalize_text(w['text'])
                # その単語がどの列（baseline）に属するか判定
                col_idx = self._get_col_index(w['x0'], col_baselines)
                row_str += f"<col:{col_idx}, x:{int(w['x0']):03d}> {text} "
            lines.append(row_str)

        return "\n".join(lines), col_baselines

    def _cluster_coordinates(self, coords):
        if not coords: return []
        coords.sort()
        clusters = [coords[0]]
        for c in coords[1:]:
            # 設定した x_tolerance を超える隙間があれば「新しい列」とみなす
            if c > clusters[-1] + self.x_tolerance:
                clusters.append(c)
        return clusters

    def _get_col_index(self, x, baselines):
        for i, b in enumerate(baselines):
            # 最も近い基準線を探す
            if abs(x - b) <= self.x_tolerance:
                return i + 1
        return 1

    def _normalize_text(self, text):
        t = text.replace('△', '-').replace('▲', '-').replace(',', '')
        if t.startswith('(') and t.endswith(')'):
            t = '-' + t[1:-1]
        return t

# --- Streamlit UI ---
st.set_page_config(page_title="Financial Col-Tagging Tester", layout="wide")

st.title("📑 Dynamic Col-Tagging Tester")
st.markdown("""
このツールは、PDF内のテキスト座標をスキャンし、**ページごとに異なる列構造（基準線）を自動特定**します。
これにより、複雑な持分変動計算書などでも「何列目のデータか」をAIが把握可能になります。
""")

st.sidebar.header("Tuning Parameters")
x_tol = st.sidebar.slider("X Tolerance (列の結合感度)", 1, 100, 20, help="この範囲内のx座標は同じ列として扱われます。")
y_tol = st.sidebar.slider("Y Tolerance (行の結合感度)", 1, 20, 3, help="この範囲内のy座標は同じ行として扱われます。")

uploaded_file = st.file_uploader("決算短信（PDF）をアップロード", type="pdf")

if uploaded_file:
    streamer = UniversalFinancialStreamer(x_tolerance=x_tol, y_tolerance=y_tol)
    output = streamer.process_pdf(uploaded_file)
    
    st.subheader("分析結果: 幾何学的ストリーム出力")
    st.text_area("AI用入力データ形式", output, height=700)
    
    # ページごとの列検出数をサマリー表示
    if "Detected" in output:
        st.sidebar.success("列解析完了")