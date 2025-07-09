# ========== 文件1: app.py ==========
"""
珠宝销售提成计算系统 - 精简云端版
直接可用，包含所有核心功能
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io

# 页面配置
st.set_page_config(
    page_title="珠宝销售提成计算系统",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========== 配置数据 ==========
# 不计提成产品列表（简化版，实际使用时补充完整73个）
NO_COMMISSION_PRODUCTS = [
    "3D硬金方糖珠", "3D硬金玫瑰花戒指（配石榴石/珍珠）",
    "3D硬金手串聚宝盆", "3D硬金转运珠", "贝珠手链"
]

# A1类型提成率配置
def get_a1_commission_rate(product_type, discount_rate):
    """获取A1类型提成率"""
    if product_type in NO_COMMISSION_PRODUCTS:
        return 0
    
    # 第1层：钻石、编织费、玉器、配件
    if product_type in ["钻石", "编织费", "玉器", "配件"]:
        if discount_rate >= 0.99: return 0.06
        elif discount_rate >= 0.95: return 0.055
        elif discount_rate >= 0.90: return 0.05
        elif discount_rate >= 0.85: return 0.045
        elif discount_rate >= 0.80: return 0.04
        elif discount_rate >= 0.75: return 0.03
        elif discount_rate >= 0.70: return 0.02
        elif discount_rate >= 0.65: return 0.01
        else: return 0
    
    # 第2层：手表、银饰件、18K金件、珍珠
    elif product_type in ["手表", "银饰件", "18K金件", "珍珠"]:
        if discount_rate >= 0.99: return 0.04
        elif discount_rate >= 0.95: return 0.035
        elif discount_rate >= 0.90: return 0.03
        elif discount_rate >= 0.85: return 0.025
        elif discount_rate >= 0.80: return 0.02
        elif discount_rate >= 0.75: return 0.01
        elif discount_rate >= 0.60: return 0.005
        else: return 0
    
    # 第3层：3D硬金、精品黄金、铂金件、足金镶宝石
    elif product_type in ["3D硬金", "精品黄金", "铂金件", "足金镶宝石"]:
        if discount_rate >= 0.99: return 0.03
        elif discount_rate >= 0.95: return 0.025
        elif discount_rate >= 0.90: return 0.02
        elif discount_rate >= 0.85: return 0.015
        elif discount_rate >= 0.80: return 0.01
        elif discount_rate >= 0.75: return 0.005
        else: return 0
    
    # 第4层：秒杀类
    elif product_type == "秒杀类":
        if discount_rate >= 0.99: return 0.025
        elif discount_rate >= 0.95: return 0.02
        elif discount_rate >= 0.90: return 0.015
        elif discount_rate >= 0.85: return 0.005
        else: return 0
    
    return 0

# ========== 核心功能函数 ==========
def identify_commission_type(order_df):
    """识别订单的提成类型"""
    has_sales_piece = any((order_df['状态'] == '销售') & (order_df['计价方式'] == '件数'))
    has_sales_weight = any((order_df['状态'] == '销售') & (order_df['计价方式'] == '重量'))
    has_recycle_piece = any((order_df['状态'] == '回收') & (order_df['计价方式'] == '件数'))
    has_recycle_weight = any((order_df['状态'] == '回收') & (order_df['计价方式'] == '重量'))
    
    if has_sales_piece and not has_sales_weight and not has_recycle_piece and not has_recycle_weight:
        return 'A1'
    elif not has_sales_piece and has_sales_weight and not has_recycle_piece and not has_recycle_weight:
        return 'A2'
    elif has_sales_piece and has_sales_weight and not has_recycle_piece and not has_recycle_weight:
        return 'A3'
    elif not has_sales_piece and has_sales_weight and not has_recycle_piece and has_recycle_weight:
        return 'B1'
    elif not has_sales_piece and has_sales_weight and (has_recycle_piece or has_recycle_weight):
        return 'B2'
    elif has_sales_piece and not has_sales_weight and has_recycle_weight:
        return 'B3'
    elif has_sales_piece and not has_sales_weight and has_recycle_piece and not has_recycle_weight:
        return 'B4'
    else:
        return '未识别'

def calculate_commission(df):
    """计算提成主函数"""
    # 初始化提成列
    df['提成类型'] = ''
    df['标价折扣率'] = 0
    df['标价提成率'] = 0
    df['标价提成'] = 0
    df['增购金重提成'] = 0
    df['工费提成'] = 0
    df['旧料提成'] = 0
    df['整单提成'] = 0
    
    # 按订单号分组处理
    for order_num in df['销售单号'].unique():
        order_mask = df['销售单号'] == order_num
        order_df = df[order_mask]
        
        # 识别提成类型
        commission_type = identify_commission_type(order_df)
        df.loc[order_mask, '提成类型'] = commission_type
        
        # 根据类型计算提成
        if commission_type == 'A1':
            # 计算A1类型提成 - 优化为向量化操作
            valid_price_mask = order_df['标签价'] > 0
            if valid_price_mask.any():
                valid_rows = order_df[valid_price_mask]
                
                discount_rates = valid_rows['最终售价'] / valid_rows['标签价']
                df.loc[valid_rows.index, '标价折扣率'] = discount_rates
                
                commission_rates = valid_rows.apply(
                    lambda row: get_a1_commission_rate(
                        row['货品种类'], 
                        row['最终售价'] / row['标签价']
                    ), 
                    axis=1
                )
                df.loc[valid_rows.index, '标价提成率'] = commission_rates
                df.loc[valid_rows.index, '标价提成'] = valid_rows['最终售价'] * commission_rates
        
        elif commission_type == 'A2':
            # A2类型：销售(重量) - 优化为向量化操作
            sales_rows = order_df[order_df['状态'] == '销售']
            
            if not sales_rows.empty:
                valid_gold_mask = (sales_rows['当天金价'] > 0) & (sales_rows['实销金价（不含工费）'] > 0)
                if valid_gold_mask.any():
                    valid_gold_rows = sales_rows[valid_gold_mask]
                    price_discounts = valid_gold_rows['当天金价'] - valid_gold_rows['实销金价（不含工费）']
                    
                    rates = pd.cut(price_discounts, 
                                 bins=[-np.inf, 10, 20, 30, 40, 50, np.inf],
                                 labels=[5, 4, 3, 2, 1, 0.5],
                                 right=True).astype(float)
                    
                    gold_commissions = valid_gold_rows['金重'] * rates
                    df.loc[valid_gold_rows.index, '增购金重提成'] = gold_commissions
                
                valid_labor_mask = sales_rows['原精品工费'] > 0
                if valid_labor_mask.any():
                    valid_labor_rows = sales_rows[valid_labor_mask]
                    labor_discounts = valid_labor_rows['零售工费'] / valid_labor_rows['原精品工费']
                    
                    labor_rates = pd.cut(labor_discounts,
                                       bins=[-np.inf, 0.80, 0.85, 0.90, 0.95, 0.99, np.inf],
                                       labels=[0, 0.01, 0.02, 0.03, 0.04, 0.05],
                                       right=False).astype(float)
                    
                    labor_commissions = valid_labor_rows['零售工费'] * labor_rates
                    df.loc[valid_labor_rows.index, '工费提成'] = labor_commissions
        
        # 计算整单提成（只在首行显示） - 优化为单次计算
        commission_columns = ['标价提成', '增购金重提成', '工费提成', '旧料提成']
        order_total = df.loc[order_mask, commission_columns].sum().sum()
        first_row_idx = order_df.index[0]
        df.loc[first_row_idx, '整单提成'] = order_total
    
    return df

# ========== Streamlit 界面 ==========
def main():
    st.title("💎 珠宝销售提成计算系统")
    st.markdown("---")
    
    # 侧边栏
    with st.sidebar:
        st.header("📊 系统功能")
        st.info(
            """
            **功能特点：**
            - 支持7种提成类型
            - 自动识别计算规则
            - 实时数据验证
            - 一键导出结果
            """
        )
        
        st.header("📝 使用说明")
        st.markdown(
            """
            1. 上传Excel文件
            2. 系统自动验证数据
            3. 点击计算提成
            4. 查看结果并导出
            """
        )
    
    # 主界面
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("📤 第一步：上传数据")
        uploaded_file = st.file_uploader(
            "选择Excel文件",
            type=['xlsx', 'xls'],
            help="请上传包含销售数据的Excel文件"
        )
    
    with col2:
        st.header("📋 数据要求")
        st.warning(
            """
            必需的列：
            - 销售单号
            - 状态
            - 计价方式
            - 标签价
            - 最终售价
            - 货品种类
            """
        )
    
    if uploaded_file is not None:
        try:
            # 读取数据
            df = pd.read_excel(uploaded_file)
            st.success(f"✅ 成功读取 {len(df)} 条数据")
            
            # 数据预览
            with st.expander("📊 查看数据预览", expanded=True):
                st.dataframe(df.head(10))
            
            # 数据验证
            st.header("🔍 第二步：数据验证")
            col1, col2, col3 = st.columns(3)
            
            # 检查必需列
            required_cols = ['销售单号', '状态', '计价方式', '标签价', '最终售价']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            with col1:
                if missing_cols:
                    st.error(f"❌ 缺少列：{', '.join(missing_cols)}")
                else:
                    st.success("✅ 必需列完整")
            
            with col2:
                orders = df['销售单号'].nunique()
                st.metric("订单数", f"{orders:,}")
            
            with col3:
                total_amount = df['总实收金额'].sum() if '总实收金额' in df.columns else 0
                st.metric("销售总额", f"¥{total_amount:,.2f}")
            
            # 计算按钮
            st.header("💰 第三步：计算提成")
            
            if st.button("🚀 开始计算", type="primary", use_container_width=True):
                with st.spinner("正在计算提成..."):
                    # 执行计算
                    result_df = calculate_commission(df.copy())
                    st.session_state['result_df'] = result_df
                    st.success("✅ 计算完成！")
            
            # 显示结果
            if 'result_df' in st.session_state:
                st.header("📊 计算结果")
                
                result_df = st.session_state['result_df']
                
                # 结果统计
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    total_commission = result_df['整单提成'].sum()
                    st.metric("提成总额", f"¥{total_commission:,.2f}")
                
                with col2:
                    avg_rate = total_commission / result_df['总实收金额'].sum() if result_df['总实收金额'].sum() > 0 else 0
                    st.metric("平均提成率", f"{avg_rate:.2%}")
                
                with col3:
                    a_types = result_df[result_df['提成类型'].str.startswith('A')]['销售单号'].nunique()
                    st.metric("A类订单", f"{a_types}")
                
                with col4:
                    b_types = result_df[result_df['提成类型'].str.startswith('B')]['销售单号'].nunique()
                    st.metric("B类订单", f"{b_types}")
                
                # 结果表格
                with st.expander("📋 查看详细结果", expanded=True):
                    # 选择显示的列
                    display_cols = ['销售单号', '主销', '客户姓名', '提成类型', 
                                   '标价提成', '增购金重提成', '工费提成', '旧料提成', '整单提成']
                    available_cols = [col for col in display_cols if col in result_df.columns]
                    st.dataframe(result_df[available_cols])
                
                # 下载结果
                st.header("💾 第四步：导出结果")
                
                # 生成Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    result_df.to_excel(writer, sheet_name='提成明细', index=False)
                    
                    # 生成汇总表
                    summary = result_df.groupby('主销').agg({
                        '销售单号': 'nunique',
                        '整单提成': 'sum'
                    }).round(2)
                    summary.to_excel(writer, sheet_name='销售员汇总')
                
                output.seek(0)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        label="📥 下载计算结果",
                        data=output,
                        file_name=f"提成计算_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                
                with col2:
                    # CSV下载选项
                    csv = result_df.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(
                        label="📥 下载CSV格式",
                        data=csv,
                        file_name=f"提成计算_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                
        except Exception as e:
            st.error(f"❌ 处理文件时出错：{str(e)}")
            st.info("请检查文件格式是否正确")

if __name__ == "__main__":
    main()

# ========== 文件2: requirements.txt ==========
"""
streamlit==1.28.1
pandas==2.0.3
numpy==1.24.3
openpyxl==3.1.2
xlsxwriter==3.1.3
"""

# ========== 文件3: README.md ==========
"""
# 💎 珠宝销售提成计算系统

## 功能特点
- 🔍 自动识别7种提成类型
- 💰 精确计算各项提成
- 📊 实时数据验证
- 💾 一键导出结果

## 使用方法
1. 上传销售数据Excel文件
2. 系统自动验证数据完整性
3. 点击"开始计算"按钮
4. 查看结果并下载

## 提成类型说明
- A1: 销售(件数)
- A2: 销售(重量)
- A3: 销售(件数+重量)
- B1: 销售(重量)+回收(重量)
- B2: 销售(重量)+回收(件数+重量)
- B3: 销售(件数)+回收(重量)
- B4: 销售(件数)+回收(件数)
"""
