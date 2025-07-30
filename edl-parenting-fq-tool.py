import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import re

# App 設定
st.set_page_config(page_title="Qforia", layout="wide")

# 隱藏 Streamlit 的預設選單和頁首工具列
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

st.title("🔍 FQ查詢擴展模擬器-EDLx親子天下")

# 側邊欄：API 金鑰輸入與查詢
st.sidebar.header("設定")
gemini_key = st.sidebar.text_input("Gemini API 金鑰", type="password")
user_query = st.sidebar.text_area("輸入您的查詢", "哪款電動 SUV 最適合開上雷尼爾山？", height=120)
mode = st.sidebar.radio("搜尋模式", ["AI 總覽 (簡易)", "AI 模式 (複雜)"])

# 版權聲明
st.sidebar.markdown("---")
st.sidebar.caption("此工具為「EDL授權給親子天下集團使用，授權時間至2025年」")


# 設定 Gemini
if gemini_key:
    genai.configure(api_key=gemini_key)
    # 確保您使用的模型能良好支援較長/複雜的 JSON 輸出。
    # 使用者模型 "gemini-2.5-flash-preview-05-20" 可能是一個特定版本；
    # 如果出現問題，可以考慮嘗試 "gemini-1.5-flash-latest" 或 "gemini-1.5-pro-latest"。
    model = genai.GenerativeModel("gemini-1.5-flash-latest") # 使用一個常見的最新 flash 模型
else:
    st.error("請輸入您的 Gemini API 金鑰以繼續。")
    st.stop()

# 包含詳細思維鏈 (Chain-of-Thought) 邏輯的提示
def QUERY_FANOUT_PROMPT(q, mode):
    min_queries_simple = 10
    min_queries_complex = 20

    # 根據模式選擇不同的查詢數量說明
    if mode == "AI 總覽 (簡易)":
        num_queries_instruction = (
            f"首先，分析使用者查詢：「{q}」。根據其複雜度和「{mode}」模式，"
            f"**你必須決定一個最佳的查詢生成數量。** "
            f"這個數量必須 **至少為 {min_queries_simple}**。 "
            f"對於一個直接的查詢，生成大約 {min_queries_simple}-{min_queries_simple + 2} 個查詢可能就足夠了。"
            f"如果查詢有幾個不同的方面或常見的後續問題，目標可以設定在稍高的數量，例如 {min_queries_simple + 3}-{min_queries_simple + 5} 個查詢。"
            f"請簡要說明你為何選擇這個特定的查詢數量。查詢本身應該範圍明確且高度相關。"
        )
    else:  # AI 模式 (複雜)
        num_queries_instruction = (
            f"首先，分析使用者查詢：「{q}」。根據其複雜度和「{mode}」模式，"
            f"**你必須決定一個最佳的查詢生成數量。** "
            f"這個數量必須 **至少為 {min_queries_complex}**。 "
            f"對於需要探索不同角度、子主題、比較或更深層含義的多面向查詢，"
            f"你應該生成一套更全面的查詢，可能在 {min_queries_complex + 5}-{min_queries_complex + 10} 個之間，如果查詢特別廣泛或深入，甚至可以更多。"
            f"請簡要說明你為何選擇這個特定的查詢數量。查詢應該多樣化且深入。"
        )

    return (
        f"You are simulating Google's AI Mode query fan-out process for generative search systems.\n"
        f"The user's original query is: \"{q}\". The selected mode is: \"{mode}\".\n\n"
        f"**Your first task is to determine the total number of queries to generate and the reasoning for this number, based on the instructions below:**\n"
        f"{num_queries_instruction}\n\n"
        f"**Once you have decided on the number and the reasoning, generate exactly that many unique synthetic queries.**\n"
        "Each of the following query transformation types MUST be represented at least once in the generated set, if the total number of queries you decide to generate allows for it (e.g., if you generate 12 queries, try to include all 6 types at least once, and then add more of the relevant types):\n"
        "1. Reformulations\n2. Related Queries\n3. Implicit Queries\n4. Comparative Queries\n5. Entity Expansions\n6. Personalized Queries\n\n"
        "The 'reasoning' field for each *individual query* should explain why that specific query was generated in relation to the original query, its type, and the overall user intent.\n"
        "Do NOT include queries dependent on real-time user history or geolocation.\n\n"
        "**IMPORTANT LANGUAGE REQUIREMENT: All generated 'query', 'user_intent', and 'reasoning' values inside the 'expanded_queries' array MUST be in Traditional Chinese (Taiwan).**\n\n"
        "Return only a valid JSON object. The JSON object should strictly follow this format:\n"
        "{\n"
        "  \"generation_details\": {\n"
        "    \"target_query_count\": 12, // This is an EXAMPLE number; you will DETERMINE the actual number based on your analysis.\n"
        "    \"reasoning_for_count\": \"The user query was moderately complex, so I chose to generate slightly more than the minimum for a simple overview to cover key aspects like X, Y, and Z.\" // This is an EXAMPLE reasoning; provide your own.\n"
        "  },\n"
        "  \"expanded_queries\": [\n"
        "    // Array of query objects. The length of this array MUST match your 'target_query_count'.\n"
        "    {\n"
        "      \"query\": \"Example query 1...\",\n"
        "      \"type\": \"reformulation\",\n"
        "      \"user_intent\": \"Example intent...\",\n"
        "      \"reasoning\": \"Example reasoning for this specific query...\"\n"
        "    },\n"
        "    // ... more query objects ...\n"
        "  ]\n"
        "}"
    )

# 查詢擴展生成函數
def generate_fanout(query, mode):
    prompt = QUERY_FANOUT_PROMPT(query, mode)
    try:
        response = model.generate_content(prompt)
        json_text = response.text.strip()
        
        # 清理潛在的 markdown 程式碼區塊標記
        if json_text.startswith("```json"):
            json_text = json_text[7:]
        if json_text.endswith("```"):
            json_text = json_text[:-3]
        json_text = json_text.strip()

        data = json.loads(json_text)
        generation_details = data.get("generation_details", {})
        expanded_queries = data.get("expanded_queries", [])

        # 儲存詳細資訊以供顯示
        st.session_state.generation_details = generation_details

        return expanded_queries
    except json.JSONDecodeError as e:
        st.error(f"🔴 解析 Gemini 回應的 JSON 失敗：{e}")
        st.text("導致錯誤的原始回應：")
        st.text(json_text if 'json_text' in locals() else "無 (在 json_text 指派前發生錯誤)")
        st.session_state.generation_details = None
        return None
    except Exception as e:
        st.error(f"🔴 產生過程中發生未預期的錯誤：{e}")
        if hasattr(response, 'text'):
             st.text("原始回應內容 (若有)：")
             st.text(response.text)
        st.session_state.generation_details = None
        return None

# 如果 session_state 中不存在 generation_details，則進行初始化
if 'generation_details' not in st.session_state:
    st.session_state.generation_details = None

# 產生並顯示結果
if st.sidebar.button("執行查詢擴展 🚀"):
    # 清除先前的詳細資訊
    st.session_state.generation_details = None
    
    if not user_query.strip():
        st.warning("⚠️ 請輸入查詢內容。")
    else:
        with st.spinner("🤖 正在使用 Gemini 產生查詢擴展... 請稍候..."):
            results = generate_fanout(user_query, mode)

        if results: # 檢查 results 是否不為 None 且不為空
            st.success("✅ 查詢擴展完成！")

            # 如果有可用的生成計數理由，則顯示
            if st.session_state.generation_details:
                details = st.session_state.generation_details
                generated_count = len(results)
                target_count_model = details.get('target_query_count', 'N/A')
                reasoning_model = details.get('reasoning_for_count', '模型未提供。')

                st.markdown("---")
                st.subheader("🧠 模型的查詢生成計畫")
                st.markdown(f"🔹 **模型決定的目標查詢數量：** `{target_count_model}`")
                st.markdown(f"🔹 **模型的數量決策理由：** _{reasoning_model}_")
                st.markdown(f"🔹 **實際產生的查詢數量：** `{generated_count}`")
                st.markdown("---")
                
                if isinstance(target_count_model, int) and target_count_model != generated_count:
                    st.warning(f"⚠️ 注意：模型目標產生 {target_count_model} 個查詢，但實際產生了 {generated_count} 個。")
            else:
                st.info("ℹ️ 模型的日應中未包含生成細節 (目標數量、理由)。")


            df = pd.DataFrame(results)
            # 調整欄位名稱為中文以利顯示，但保持原始欄位名稱在 DataFrame 中
            display_df = df.rename(columns={
                "query": "查詢語句",
                "type": "類型",
                "user_intent": "使用者意圖",
                "reasoning": "生成理由"
            })
            st.dataframe(display_df, use_container_width=True, height=(min(len(df), 20) + 1) * 35 + 3) # 動態高度

            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("📥 下載 CSV", data=csv, file_name="qforia_輸出.csv", mime="text/csv")
        
        elif results is None: # 在 generate_fanout 中發生錯誤
            # 錯誤訊息已由 generate_fanout 顯示
            pass
        else: # 處理空的結果列表 (空列表，非 None)
            st.warning("⚠️ 未產生任何查詢。模型回傳了空列表，或發生了問題。")
