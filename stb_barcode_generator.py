import io
import zipfile
import barcode
from barcode.writer import ImageWriter
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title='STBバーコード生成ツール', page_icon='📦', layout='centered'
)

st.title('📦 STBバーコード一括生成・テストツール')
st.write(
    'CSVファイル（A列に管理番号等が入ったファイル）をアップロードするだけで、理想の見た目でバーコードを生成できます。'
)

# 1. CSVファイルのアップロード（列選択などは省き、自動的に先頭列をターゲットにします）
uploaded_file = st.file_uploader(
    'STBリストのCSVファイルを選択してください', type=['csv']
)

if uploaded_file is not None:
  # CSVを読み込む（ヘッダーなし、または先頭行をデータとして扱う場合などに対応できるよう柔軟に）
  df = pd.read_csv(uploaded_file)

  # 自動的に先頭の列（A列）をターゲット列として使用する
  target_column = df.columns[0]

  # データの抽出と指数表記（1.96222E+11など）の自動修復
  cleaned_data_list = []
  for raw_data in df[target_column]:
    try:
      if isinstance(raw_data, float) or (
          isinstance(raw_data, str) and 'e' in raw_data.lower()
      ):
        val = str(int(float(raw_data)))
      else:
        val = str(raw_data).strip()
    except Exception:
      val = str(raw_data).strip()

    if val and val.lower() != 'nan':
      cleaned_data_list.append(val)

  st.success(
      f'✨ CSVから **{len(cleaned_data_list)}件** のデータを正常に読み込みました！'
  )

  # 2. バーコードの設定項目（見た目の微調整）
  st.subheader('⚙️ バーコードの見た目調整')
  col1, col2 = st.columns(2)

  with col1:
    module_height = st.slider(
        'バーの高さ (module_height)',
        min_value=5.0,
        max_value=30.0,
        value=15.0,
        step=1.0,
    )
    font_size = st.slider(
        '文字の大きさ (font_size)', min_value=6, max_value=20, value=10, step=1
    )

  with col2:
    text_distance = st.slider(
        '文字とバーの距離 (text_distance)',
        min_value=1.0,
        max_value=20.0,
        value=5.0,
        step=1.0,
    )
    module_width = st.slider(
        'バーの太さ (module_width)',
        min_value=1.0,
        max_value=1.0,  # 安定した太さ
        value=0.3,
        step=0.05,
    )

  # 3. プレビュー確認（先頭の1件目を例として表示）
  if cleaned_data_list:
    st.subheader('🔍 プレビュー（最初の1件目の確認）')
    sample_data = cleaned_data_list[0]

    try:
      code39 = barcode.get_barcode_class('code39')
      barcode_instance = code39(sample_data, writer=ImageWriter())

      options = {
          'module_width': module_width,
          'module_height': module_height,
          'font_size': font_size,
          'text_distance': text_distance,
          'quiet_zone': 6.5,
          'write_text': True,
      }

      # 描画文字を「両端アスタリスク ＆ 文字間にスペース」が入った形式にカスタマイズ
      spaced_text = ' '.join(list(sample_data))
      barcode_instance.default_text = f'* {spaced_text} *'

      sample_rv = io.BytesIO()
      barcode_instance.write(sample_rv, options=options)
      sample_rv.seek(0)

      st.image(
          sample_rv, caption=f'サンプル確認: *{spaced_text}*', use_container_width=True
      )
    except Exception as e:
      st.error(f'プレビュー生成エラー: {e}')

    # 4. 一括生成・ZIPダウンロードボタン
    st.markdown('---')
    if st.button('📦 すべてのバーコード画像をZIPで一括生成する'):
      zip_buffer = io.BytesIO()
      success_count = 0

      with zipfile.ZipFile(
          zip_buffer, 'w', zipfile.ZIP_DEFLATED
      ) as zip_file:
        for clean_data in cleaned_data_list:
          try:
            code39 = barcode.get_barcode_class('code39')
            barcode_instance = code39(clean_data, writer=ImageWriter())

            options = {
                'module_width': module_width,
                'module_height': module_height,
                'font_size': font_size,
                'text_distance': text_distance,
                'quiet_zone': 6.5,
                'write_text': True,
            }

            spaced_text = ' '.join(list(clean_data))
            barcode_instance.default_text = f'* {spaced_text} *'

            rv = io.BytesIO()
            barcode_instance.write(rv, options=options)

            zip_file.writestr(f'stb_barcode_{clean_data}.png', rv.getvalue())
            success_count += 1
          except Exception:
            pass

      if success_count > 0:
        st.success(
            f'✨ {success_count}件のバーコード生成が完了しました！下のボタンからダウンロードできます。'
        )
        zip_buffer.seek(0)
        st.download_button(
            label='📥 バーコード画像をZIPで一括ダウンロード',
            data=zip_buffer,
            file_name='stb_barcodes.zip',
            mime='application/zip',
        )
