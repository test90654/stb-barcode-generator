import io
import zipfile
import barcode
from barcode.writer import ImageWriter
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title='STBバーコード一括生成ツール', page_icon='📦', layout='centered'
)

st.title('📦 STB（セットトップボックス）用バーコード一括生成')
st.write(
    'STBの管理番号やシリアルナンバーが記載されたCSVファイルをアップロードすると、Code 39のバーコード画像をまとめて生成・ダウンロードできます。'
)
st.write(
    '※Excel等で指数表記（例: 1.96222E+11）に変換されてしまった数値も、自動で正しい文字列に修復して処理します。'
)

# 1. ファイル選択（アップロード）ボタン
uploaded_file = st.file_uploader(
    'STBリストのCSVファイルを選択してください', type=['csv']
)

if uploaded_file is not None:
  # CSVを読み込む
  df = pd.read_csv(uploaded_file)

  st.subheader('読み込んだデータ（プレビュー）')
  st.dataframe(df.head())

  # 2. バーコード化したい列の選択
  columns = df.columns.tolist()
  target_column = st.selectbox(
      'バーコード化する文字列（STB番号など）が入っている列を選択してください:', columns
  )

  # 3. 実行ボタン
  if st.button('STBバーコードを一括生成する'):
    code39 = barcode.get_barcode_class('code39')

    # 生成した画像をZIPにまとめるためのメモリ上の準備
    zip_buffer = io.BytesIO()
    success_count = 0

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
      for index, row in df.iterrows():
        raw_data = row[target_column]

        # 指数表記（例: 1.96222E+11）や小数点を自動修復する処理
        try:
          if isinstance(raw_data, float) or (
              isinstance(raw_data, str) and 'e' in raw_data.lower()
          ):
            data = str(int(float(raw_data)))
          else:
            data = str(raw_data).strip()
        except Exception:
          data = str(raw_data).strip()

        # 空白や欠損値（NaN）の場合はスキップ
        if not data or data.lower() == 'nan':
          continue

        try:
          # バーコード画像をメモリ上に生成
          rv = io.BytesIO()
          barcode_instance = code39(data, writer=ImageWriter())
          barcode_instance.write(rv)

          # ZIPファイル内に追加
          zip_file.writestr(f'stb_barcode_{data}.png', rv.getvalue())
          success_count += 1
        except Exception as e:
          st.error(f'エラー ({data}): {e}')

    if success_count > 0:
      st.success(
          f'✨ {success_count}件のSTBバーコード生成が完了しました！下のボタンからZIPでダウンロードできます。'
      )

      # 4. ZIPファイルのダウンロードボタン
      zip_buffer.seek(0)
      st.download_button(
          label='📥 STBバーコード画像をZIPで一括ダウンロード',
          data=zip_buffer,
          file_name='stb_barcodes.zip',
          mime='application/zip',
      )
