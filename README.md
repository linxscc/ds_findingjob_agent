# ds_findingjob_agent

 # 1. 安装依赖
  
  python -m venv .venv
  .venv\Scripts\activate

  pip install -r requirements.txt
  playwright install chromium

  # 2. 修改 config/settings.yaml 中的 MySQL 配置

  # 3. 采集所有启用公司的岗位
  python main.py collect

  # 4. 导出 Excel
  python main.py collect -f excel

  # 5. 半自动导入（粘贴微信文本）
  python main.py manual
