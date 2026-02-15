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
                # --- 【変更点】正規化のタイミングを変更 ---
                # 元のテキストを保持しつつ、判定とID付与を行う
                raw_text = w['text']
                col_idx = self._get_col_index(w['x0'], col_baselines)
                
                # 数値候補かどうか判定してIDを振る
                tagged_text = self._apply_value_id(raw_text)
                
                row_str += f"<col:{col_idx}, x:{int(w['x0']):03d}> {tagged_text} "
            lines.append(row_str)

        return "\n".join(lines), col_baselines

    # --- 【新規・変更点】数値可能性の最大抽出ロジック ---
    def _is_numeric_candidate(self, text):
        """数字（全角・半角）または特定の通貨・計算記号が含まれているか判定"""
        has_digit = any(char.isdigit() for char in text)
        has_currency_sym = any(char in "△▲¥$€%.," for char in text)
        return has_digit or has_currency_sym

    def _mask_text(self, text):
        """数値を 'x' に置換しつつ、単位や記号（兆、円、％、△等）を保護する"""
        # 半角・全角数字をすべて 'x' に置換
        masked = re.sub(r'[0-9０-９]', 'x', text)
        return masked
    
    def _apply_value_id(self, text):
        """
        トークン内の数値部分(2,589)だけを見つけ出し、
        ID化(<v_001:2589>)して、前後の文字(億円となり、)はそのまま残す。
        """
        # 数値（カンマ、小数点、前置の△▲、後続の%を含む）を抽出する正規表現
        # 兆、億、万などの漢字単位はあえてAIに解釈させるため抽出対象から外す（外側に残す）
        num_pattern = r'[△▲-]?[0-9０-９,，.．]+%?'

        def replace_match(match):
            raw_num = match.group(0)
            self.val_counter += 1
            v_id = f"v_{self.val_counter:03d}"
            
            # 計算の邪魔になるカンマを消去
            val_for_ai = raw_num.replace(',', '').replace('，', '')
            
            if self.mask_numbers:
                # マスキング時は数値部分のみを x に
                masked_val = self._mask_text(val_for_ai)
                return f"<{v_id}:{masked_val}>"
            else:
                return f"<{v_id}:{val_for_ai}>"

        # テキスト内の数値部分だけを置換
        return re.sub(num_pattern, replace_match, text)

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

    # _normalize_text は _apply_value_id 内に統合されたため廃止可能ですが、
    # 互換性のため、あるいはシンプルな前処理が必要な場合のために最小限で残します。
    def _normalize_text(self, text):
        return text.replace(',', '')

# --- Streamlit UI ---
st.set_page_config(page_title="Financial ID-Tagging Tester", layout="wide")

st.title("📑 Universal Financial Streamer")
st.markdown("""
このツールは、PDF内の座標から**「幾何学的構造（列）」**と**「論理的構造（ID）」**を抽出します。
数値可能性のあるトークンはすべて `v_id` が付与され、AIによる解釈を助けます。
""")

# サイドバーの設定
st.sidebar.header("Tuning Parameters")
x_tol = st.sidebar.slider("X Tolerance (列の結合感度)", 1, 100, 20, help="この範囲内のx座標は同じ列として扱われます。")
y_tol = st.sidebar.slider("Y Tolerance (行の結合感度)", 1, 20, 11, help="この範囲内のy座標は同じ行として扱われます。")

# マスキング切り替えスイッチ
mask_on = st.sidebar.checkbox(
    "数値をマスキングする (xxx置換)", 
    value=False, 
    help="ONにすると <v_id:1,234円> が <v_id:x,xxx円> のように置換されます。"
)

uploaded_file = st.file_uploader("決算短信（PDF）をアップロード", type="pdf")

if uploaded_file:
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
        st.sidebar.success("解析完了")