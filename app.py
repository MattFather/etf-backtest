import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import uuid

# --- 網頁設定 ---
st.set_page_config(page_title="ETF 綜合回測戰情室", page_icon="📊", layout="wide")

st.title("📊 ETF 多標的 & 定期定額 綜合回測戰情室")
st.markdown("建立多組回測任務，支援「單筆投入」與「定期定額」混搭，一鍵比較不同標的與策略的長期複利績效！")

# --- 初始化 Session State ---
if 'backtest_tasks' not in st.session_state:
    st.session_state.backtest_tasks = [
        {
            "id": str(uuid.uuid4())[:8],
            "ticker": "00929.TW",
            "start_date": date(2024, 5, 30),
            "initial": 400000,
            "dca": 0
        },
        {
            "id": str(uuid.uuid4())[:8],
            "ticker": "00713.TW",
            "start_date": date(2024, 6, 12),
            "initial": 550000,
            "dca": 0
        }
    ]

# --- 側邊欄：新增回測任務與全域設定 ---
with st.sidebar:
    st.header("⚙️ 1. 全域交易成本設定")
    fee_rate = st.number_input("買進手續費率 (%)", value=0.1425, format="%.4f", help="若券商有優惠請自行修改")
    min_fee = st.number_input("單筆最低手續費 (元)", min_value=0, value=20)
    
    st.markdown("---")
    st.header("➕ 2. 新增回測任務")
    
    ticker_input = st.text_input("輸入 ETF 代號", value="0050.TW", help="如 0050.TW, 00878.TW")
    default_start = date.today().replace(year=date.today().year - 5)
    start_date = st.date_input("開始投入日期", value=default_start)
    
    st.subheader("資金投入模式")
    initial_investment = st.number_input("首日單筆投入金額 (元)", min_value=0, value=100000, step=10000, help="若純定期定額可設為0")
    dca_investment = st.number_input("每月定期定額金額 (元)", min_value=0, value=10000, step=1000, help="每月第一個交易日投入。若純單筆可設為0")
    
    if st.button("📥 加入回測清單", use_container_width=True):
        if initial_investment == 0 and dca_investment == 0:
            st.error("單筆和定額不能同時為 0！")
        else:
            task = {
                "id": str(uuid.uuid4())[:8],
                "ticker": ticker_input.upper(),
                "start_date": start_date,
                "initial": initial_investment,
                "dca": dca_investment
            }
            st.session_state.backtest_tasks.append(task)
            st.success(f"已加入：{ticker_input}")

    st.markdown("---")
    st.header("📋 3. 待執行任務清單")
    if len(st.session_state.backtest_tasks) == 0:
        st.info("目前尚無任務，請從上方新增。")
    else:
        for i, t in enumerate(st.session_state.backtest_tasks):
            st.write(f"**{i+1}. {t['ticker']}** | 單筆:{t['initial']//1000}k | 定額:{t['dca']//1000}k/月")
        
        col_run, col_clear = st.columns(2)
        with col_clear:
            if st.button("🗑️ 清空", use_container_width=True):
                st.session_state.backtest_tasks = []
                st.rerun()
        with col_run:
            run_button = st.button("🚀 開始回測", type="primary", use_container_width=True)

# --- 定義轉換 CSV 的函數 ---
@st.cache_data
def convert_df_to_csv(df):
    return df.to_csv(index=True).encode('utf-8-sig')

# --- 生成模擬券商對帳單 HTML + 截圖下載功能的函數 ---
def generate_brokerage_html(results_dict):
    total_pnl = 0
    total_value = 0
    total_cost = 0
    
    rows_html = ""
    for task_id, (task_info, res_df) in results_dict.items():
        last_r = res_df.iloc[-1]
        
        # 這裡提取 DRIP 策略的最終結果作為對帳單展示
        shares = int(last_r['DRIP_總張數'] * 1000)
        price = last_r['當日股價']
        market_value = last_r['DRIP_股票現值']
        cost = last_r['DRIP_持有總成本']
        
        if shares == 0:
            continue
            
        pnl = market_value - cost
        roi = (pnl / cost * 100) if cost > 0 else 0
        avg_cost = cost / shares
        
        total_pnl += pnl
        total_value += market_value
        total_cost += cost
        
        # 券商台股顏色邏輯：賺錢為紅色，賠錢為綠色
        pnl_color = "#A32020" if pnl > 0 else ("#008000" if pnl < 0 else "black")
        pnl_sign = "+" if pnl > 0 else ""
        
        # 將代號轉換為中文名稱
        ticker_name = task_info['ticker']
        name_map = {
            "00929.TW": "復華台灣科技優息",
            "00713.TW": "元大台灣高息低波",
            "0050.TW": "元大台灣50",
            "00878.TW": "國泰永續高股息",
            "0056.TW": "元大高股息"
        }
        display_name = name_map.get(ticker_name, ticker_name)
        
        # 表格每一行的 HTML
        rows_html += f"""<tr style="background-color: white; text-align: right; border-bottom: 1px solid #a0b0d0;">
<td style="text-align: center; padding: 4px; border: 1px solid #a0b0d0;"><span style="background-color: #DC765D; color: white; padding: 2px 6px; border-radius: 2px; font-size: 13px;">明細</span></td>
<td style="text-align: center; border: 1px solid #a0b0d0; color: black;">{display_name}</td>
<td style="text-align: center; border: 1px solid #a0b0d0; color: black;">現股</td>
<td style="border: 1px solid #a0b0d0; padding-right: 5px; color: black;">{shares:,}</td>
<td style="border: 1px solid #a0b0d0; padding-right: 5px; color: black;">{price:,.2f}</td>
<td style="border: 1px solid #a0b0d0; padding-right: 5px; color: black;">{market_value:,.0f}</td>
<td style="border: 1px solid #a0b0d0; padding-right: 5px; color: black;">{avg_cost:,.2f}</td>
<td style="border: 1px solid #a0b0d0; padding-right: 5px; color: black;">{cost:,.0f}</td>
<td style="color: {pnl_color}; border: 1px solid #a0b0d0; padding-right: 5px;">{pnl_sign}{pnl:,.0f}</td>
<td style="color: {pnl_color}; border: 1px solid #a0b0d0; padding-right: 5px;">{pnl_sign}{roi:.2f}%</td>
<td style="border: 1px solid #a0b0d0; padding-right: 5px; color: black;">0</td>
<td style="border: 1px solid #a0b0d0; padding-right: 5px; color: black;">0</td>
</tr>"""
        
    total_roi = (total_pnl / total_cost * 100) if total_cost > 0 else 0
    total_pnl_color = "#A32020" if total_pnl > 0 else ("#008000" if total_pnl < 0 else "black")
    total_pnl_sign = "+" if total_pnl > 0 else ""
    
    # 組合完整的 HTML UI (包含 html2canvas 腳本與下載按鈕)
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
    <style>
        body {{ font-family: 'Microsoft JhengHei', sans-serif; margin: 0; padding: 10px; }}
        .download-btn {{
            background-color: #2b7bc4; color: white; padding: 10px 20px; border: none;
            border-radius: 5px; cursor: pointer; font-size: 15px; margin-bottom: 15px;
            font-weight: bold; transition: 0.3s;
        }}
        .download-btn:hover {{ background-color: #1a5c99; }}
    </style>
</head>
<body>
    <button class="download-btn" onclick="downloadImage()">📸 下載對帳單圖片 (PNG)</button>
    
    <!-- 這是準備被截圖的區塊 -->
    <div id="capture-area" style="background-color: #f7f9fc; padding: 15px; border-radius: 5px; display: inline-block;">
        <div style="font-size: 22px; margin-bottom: 10px; color: black; min-width: 800px;">
        預估總損益:<span style="color: {total_pnl_color}; font-weight: normal;">{total_pnl_sign}{total_pnl:,.0f}</span>&nbsp;&nbsp;&nbsp;
        預估總市值:<span style="font-weight: normal;">{total_value:,.0f}</span>&nbsp;&nbsp;&nbsp;
        預估總報酬率:<span style="color: {total_pnl_color}; font-weight: normal;">{total_pnl_sign}{total_roi:.2f}%</span>&nbsp;&nbsp;&nbsp;
        <span style="font-size: 18px; font-weight: normal; color: black;">筆數:{len(results_dict)}(頁次 1/1)</span>
        </div>
        <table style="width: 100%; min-width: 1000px; border-collapse: collapse; text-align: right; font-size: 15px; border: 1px solid #a0b0d0; background-color: white;">
        <tr style="background-color: #c9d9f9; text-align: center; color: black;">
        <th style="padding: 6px; border: 1px solid #a0b0d0; font-weight: normal;">明細</th>
        <th style="padding: 6px; border: 1px solid #a0b0d0; font-weight: normal;">商品</th>
        <th style="padding: 6px; border: 1px solid #a0b0d0; font-weight: normal;">交易類別</th>
        <th style="padding: 6px; border: 1px solid #a0b0d0; font-weight: normal;">庫存股數</th>
        <th style="padding: 6px; border: 1px solid #a0b0d0; font-weight: normal;">市價</th>
        <th style="padding: 6px; border: 1px solid #a0b0d0; font-weight: normal;">市值</th>
        <th style="padding: 6px; border: 1px solid #a0b0d0; font-weight: normal;">交易成本(平均)</th>
        <th style="padding: 6px; border: 1px solid #a0b0d0; font-weight: normal;">持有成本</th>
        <th style="padding: 6px; border: 1px solid #a0b0d0; font-weight: normal;">預估損益</th>
        <th style="padding: 6px; border: 1px solid #a0b0d0; font-weight: normal;">預估報酬率</th>
        <th style="padding: 6px; border: 1px solid #a0b0d0; font-weight: normal;">保證金</th>
        <th style="padding: 6px; border: 1px solid #a0b0d0; font-weight: normal;">利息</th>
        </tr>
        {rows_html}
        </table>
    </div>

    <script>
    function downloadImage() {{
        var element = document.getElementById('capture-area');
        // scale: 2 可以讓輸出的 PNG 畫質更高(Retina級別)
        html2canvas(element, {{ scale: 2 }}).then(function(canvas) {{
            var link = document.createElement('a');
            link.download = '模擬券商對帳單.png';
            link.href = canvas.toDataURL('image/png');
            link.click();
        }});
    }}
    </script>
</body>
</html>"""
    return html

# --- 核心回測邏輯 ---
def run_single_backtest(task, fee_rate_pct, min_fee_amt):
    ticker = yf.Ticker(task['ticker'])
    start_dt = datetime.combine(task['start_date'], datetime.min.time())
    df = ticker.history(start=start_dt)
    
    if df.empty:
        return None, f"找不到標的 {task['ticker']} 的資料"
    
    # 💡 【錯誤修正：資料清洗】
    df = df.dropna(subset=['Close'])
    df['Dividends'] = df['Dividends'].fillna(0)
    
    if df.empty:
        return None, f"標的 {task['ticker']} 的有效交易資料為空"
        
    actual_fee_rate = fee_rate_pct / 100
    
    # 變數初始化
    shares_drip = 0
    cash_pool_drip = 0       
    unused_capital_drip = 0  
    deployed_capital_drip = 0 
    holding_cost_drip = 0    
    total_capital_injected = 0 
    
    shares_no = 0
    capital_cash_no = 0      
    div_cash_no = 0          
    unused_capital_no = 0
    deployed_capital_no = 0
    holding_cost_no = 0
    
    last_dca_month = -1
    history_records = []
    
    for current_date, row in df.iterrows():
        price = row['Close']
        dividend = row['Dividends']
        
        # 1. 資金注入邏輯
        injected_today = 0
        if current_date == df.index[0]:
            injected_today += task['initial']
            last_dca_month = current_date.month
            if task['initial'] == 0 and task['dca'] > 0:
                 injected_today += task['dca']
        elif task['dca'] > 0 and current_date.month != last_dca_month:
            injected_today += task['dca']
            last_dca_month = current_date.month
            
        if injected_today > 0:
            total_capital_injected += injected_today
            cash_pool_drip += injected_today
            unused_capital_drip += injected_today
            capital_cash_no += injected_today
            unused_capital_no += injected_today

        # 2. 股息發放邏輯
        if dividend > 0:
            cash_pool_drip += (shares_drip * dividend)
            div_cash_no += (shares_no * dividend) 

        # 3. 買進邏輯函數
        def buy_lots(available_cash, current_price):
            cost_per_lot = current_price * 1000
            lots = 0
            while True:
                test_lots = lots + 1
                test_cost = test_lots * cost_per_lot
                test_fee = max(min_fee_amt, int(test_cost * actual_fee_rate))
                if (test_cost + test_fee) <= available_cash:
                    lots = test_lots
                else:
                    break
            
            if lots > 0:
                stock_cost = lots * 1000 * current_price
                fee = max(min_fee_amt, int(stock_cost * actual_fee_rate))
                return lots * 1000, int(stock_cost + fee)
            return 0, 0

        # 執行 DRIP 買進
        new_shares_drip, total_cost_drip = buy_lots(cash_pool_drip, price)
        if new_shares_drip > 0:
            cash_pool_drip -= total_cost_drip
            shares_drip += new_shares_drip
            holding_cost_drip += total_cost_drip
            prin_used = min(total_cost_drip, unused_capital_drip)
            unused_capital_drip -= prin_used
            deployed_capital_drip += prin_used

        # 執行 單純領息買進
        new_shares_no, total_cost_no = buy_lots(capital_cash_no, price)
        if new_shares_no > 0:
            capital_cash_no -= total_cost_no
            shares_no += new_shares_no
            holding_cost_no += total_cost_no
            prin_used_no = min(total_cost_no, unused_capital_no)
            unused_capital_no -= prin_used_no
            deployed_capital_no += prin_used_no

        # 4. 結算每日資產
        stock_val_drip = int(shares_drip * price)
        total_val_drip = stock_val_drip + int(cash_pool_drip)
        unrealized_pnl_drip = stock_val_drip - holding_cost_drip
        total_pnl_drip = total_val_drip - total_capital_injected
        roi_stock_drip = (unrealized_pnl_drip / holding_cost_drip * 100) if holding_cost_drip > 0 else 0
        roi_total_drip = (total_pnl_drip / total_capital_injected * 100) if total_capital_injected > 0 else 0
        
        stock_val_no = int(shares_no * price)
        total_cash_no = int(capital_cash_no + div_cash_no)
        total_val_no = stock_val_no + total_cash_no
        unrealized_pnl_no = stock_val_no - holding_cost_no
        total_pnl_no = total_val_no - total_capital_injected
        roi_stock_no = (unrealized_pnl_no / holding_cost_no * 100) if holding_cost_no > 0 else 0
        roi_total_no = (total_pnl_no / total_capital_injected * 100) if total_capital_injected > 0 else 0

        history_records.append({
            "日期": current_date.strftime("%Y-%m-%d"),
            "當日股價": round(price, 2),
            "累積投入總本金": total_capital_injected,
            "DRIP_總張數": int(shares_drip // 1000),
            "DRIP_持有總成本": int(holding_cost_drip),
            "DRIP_股票現值": stock_val_drip,
            "DRIP_現金餘額": int(cash_pool_drip),
            "DRIP_總資產": total_val_drip,
            "DRIP_券商帳面投報率%": round(roi_stock_drip, 2),
            "DRIP_真實總投報率%": round(roi_total_drip, 2),
            "NoDRIP_總張數": int(shares_no // 1000),
            "NoDRIP_持有總成本": int(holding_cost_no),
            "NoDRIP_股票現值": stock_val_no,
            "NoDRIP_剩餘買股本金": int(capital_cash_no),
            "NoDRIP_累積未投入股息": int(div_cash_no),
            "NoDRIP_總資產": total_val_no,
            "NoDRIP_券商帳面投報率%": round(roi_stock_no, 2),
            "NoDRIP_真實總投報率%": round(roi_total_no, 2)
        })

    res_df = pd.DataFrame(history_records).set_index("日期")
    
    last_row = res_df.iloc[-1]
    summary = {
        "任務 ID": task['id'],
        "標的": task['ticker'],
        "總投入本金": last_row['累積投入總本金'],
        "DRIP 最終總資產": last_row['DRIP_總資產'],
        "DRIP 真實總報酬": f"{last_row['DRIP_真實總投報率%']}%",
        "領息 最終總資產": last_row['NoDRIP_總資產'],
        "領息 真實總報酬": f"{last_row['NoDRIP_真實總投報率%']}%",
        "區間": f"{res_df.index[0]} ~ {res_df.index[-1]}"
    }
    
    return res_df, summary


# --- 執行回測區塊 ---
if 'run_button' in locals() and run_button:
    results_dict = {}
    summaries = []
    
    progress_text = "回測任務執行中..."
    my_bar = st.progress(0, text=progress_text)
    
    for idx, task in enumerate(st.session_state.backtest_tasks):
        my_bar.progress((idx) / len(st.session_state.backtest_tasks), text=f"正在計算 {task['ticker']}...")
        df_res, summary_or_err = run_single_backtest(task, fee_rate, min_fee)
        
        if df_res is None:
            st.error(summary_or_err)
        else:
            results_dict[task['id']] = (task, df_res)
            summaries.append(summary_or_err)
            
    my_bar.progress(1.0, text="計算完成！")
    
    if summaries:
        st.success("✅ 所有回測任務執行完畢！")
        
        st.header("🏆 綜合績效比較總表")
        st.markdown("在此表格中，你可以直接對比不同標的與投入策略的最終財富變化。")
        sum_df = pd.DataFrame(summaries).set_index("任務 ID")
        st.dataframe(sum_df, use_container_width=True)
        
        # --- 插入模擬券商對帳單 (結合截圖按鈕) ---
        st.divider()
        st.header("📸 模擬券商庫存對帳單")
        st.markdown("以下為根據最終回測數據，即時生成的動態券商介面（點擊藍色按鈕即可下載高清對帳單圖片）：")
        
        brokerage_html = generate_brokerage_html(results_dict)
        # 動態計算 iframe 高度：基礎高度 180 + 每一列增加 50
        dynamic_height = 180 + (len(results_dict) * 50)
        components.html(brokerage_html, height=dynamic_height, scrolling=True)
        
        st.divider()
        st.header("📂 各別標的詳細報表與圖表")
        
        tabs = st.tabs([f"{t['ticker']} ({t['id']})" for t in st.session_state.backtest_tasks if t['id'] in results_dict])
        
        for tab, task_dict in zip(tabs, st.session_state.backtest_tasks):
            if task_dict['id'] not in results_dict: continue
            
            task_info, res_df = results_dict[task_dict['id']]
            
            with tab:
                st.subheader(f"📊 {task_info['ticker']} 總資產成長走勢圖")
                st.caption(f"設定條件：首日單筆 ${task_info['initial']:,.0f} | 每月定額 ${task_info['dca']:,.0f}")
                
                fig = px.line(res_df, x=res_df.index, y=["DRIP_總資產", "NoDRIP_總資產"], 
                              labels={"value": "總資產價值 (元)", "日期": "日期", "variable": "策略"},
                              color_discrete_map={"DRIP_總資產": "#00CC96", "NoDRIP_總資產": "#636EFA"})
                fig.update_layout(hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                st.plotly_chart(fig, use_container_width=True)
                
                last_r = res_df.iloc[-1]
                st.markdown("##### 📌 股息再投入 (DRIP) 最終成效")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("最終總張數", f"{last_r['DRIP_總張數']} 張")
                c2.metric("最終總資產", f"${last_r['DRIP_總資產']:,.0f}")
                c3.metric("券商帳面投報率", f"{last_r['DRIP_券商帳面投報率%']}%")
                c4.metric("真實總投報率", f"{last_r['DRIP_真實總投報率%']}%")
                
                st.markdown("##### 📌 單純領息 (股息存銀行) 最終成效")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("最終總張數", f"{last_r['NoDRIP_總張數']} 張")
                c2.metric("累積領取股息", f"${last_r['NoDRIP_累積未投入股息']:,.0f}")
                c3.metric("券商帳面投報率", f"{last_r['NoDRIP_券商帳面投報率%']}%")
                c4.metric("真實總投報率", f"{last_r['NoDRIP_真實總投報率%']}%")
                
                with st.expander("🔍 點擊查看每日明細表與下載"):
                    st.dataframe(res_df, use_container_width=True)
                    
                    csv_data = convert_df_to_csv(res_df)
                    st.download_button(
                        label=f"📥 下載 {task_info['ticker']} 完整資產明細 (CSV)",
                        data=csv_data,
                        file_name=f"{task_info['ticker'].replace('.TW', '')}_綜合回測明細.csv",
                        mime="text/csv",
                        use_container_width=True
                    )