"""生成三个复杂 PDF 测试样本：带线表格+页眉页脚、扫描件（无文字层）、双栏排版。

用法：cd testsamples && python make_samples.py
产物：table_sample.pdf / scanned_sample.pdf / twocol_sample.pdf
"""
import fitz


def make_table_sample():
    doc = fitz.open()
    page = doc.new_page()

    # 页眉（每页重复）+ 标题 + 正文
    page.insert_text((50, 40), "XX 集团内部资料·未经许可不得外传", fontname="china-s", fontsize=8)
    page.insert_text((50, 60), "2026 年上半年部门业绩汇总表", fontname="china-s", fontsize=16)
    page.insert_text((50, 90), "下表为各事业部上半年核心经营数据，数据来源：财务部季度报表。", fontname="china-s", fontsize=11)
    page.insert_text((50, 780), "第 1 页 共 2 页", fontname="china-s", fontsize=9)

    headers = ["事业部", "营收(万元)", "利润(万元)", "同比增速"]
    rows = [
        ["云服务事业部", "8,520", "1,240", "+23.5%"],
        ["数据智能事业部", "6,380", "890", "+12.1%"],
        ["企业软件事业部", "4,150", "-320", "-8.3%"],
        ["金融科技事业部", "9,760", "2,180", "+31.2%"],
    ]
    x0, y0 = 50, 120
    col_w = [120, 100, 100, 100]
    row_h = 26
    n_rows = len(rows) + 1
    total_w = sum(col_w)

    for i in range(n_rows + 1):
        y = y0 + i * row_h
        page.draw_line((x0, y), (x0 + total_w, y))
    x = x0
    for w in col_w:
        page.draw_line((x, y0), (x, y0 + n_rows * row_h))
        x += w
    page.draw_line((x, y0), (x, y0 + n_rows * row_h))

    for ci, h in enumerate(headers):
        page.insert_text((x0 + 5 + sum(col_w[:ci]), y0 + 17), h, fontname="china-s", fontsize=10)
    for ri, row in enumerate(rows):
        for ci, cell in enumerate(row):
            page.insert_text((x0 + 5 + sum(col_w[:ci]), y0 + (ri + 1) * row_h + 17),
                             cell, fontname="china-s", fontsize=10)

    # 第 2 页：页眉页脚重复 + 一段结论正文
    page2 = doc.new_page()
    page2.insert_text((50, 40), "XX 集团内部资料·未经许可不得外传", fontname="china-s", fontsize=8)
    page2.insert_text((50, 60), "分析与结论", fontname="china-s", fontsize=16)
    page2.insert_text((50, 90),
                      "上半年金融科技事业部增速最高，达到 31.2%；企业软件事业部出现亏损，"
                      "利润为 -320 万元，需要在下半年重点整改。", fontname="china-s", fontsize=11)
    page2.insert_text((50, 780), "第 2 页 共 2 页", fontname="china-s", fontsize=9)

    doc.save("table_sample.pdf")
    doc.close()
    print("生成 table_sample.pdf")


def make_scanned_sample():
    """把 13_产品增长白皮书.pdf 渲染成图片再合成 PDF —— 无文字层，模拟扫描件。"""
    src = fitz.open("../data/13_产品增长白皮书.pdf")
    out = fitz.open()
    for page in src:
        pix = page.get_pixmap(dpi=150)
        npage = out.new_page(width=page.rect.width, height=page.rect.height)
        npage.insert_image(npage.rect, stream=pix.tobytes("png"))
    out.save("scanned_sample.pdf")
    out.close()
    src.close()
    print("生成 scanned_sample.pdf")


def make_twocol_sample():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 40), "技术周报（双栏样例）", fontname="china-s", fontsize=14)

    left = ("【左栏·AI 平台组】\n本周完成向量检索服务升级，"
            "QPS 从 120 提升到 340，P99 延迟下降 42%。"
            "主要优化点是索引分片与查询缓存。\n"
            "下周计划：接入语义路由模块，"
            "预计可再降低 20% 的召回延迟。")
    right = ("【右栏·数据平台组】\n数据同步链路新增断点续传能力，"
             "凌晨批处理任务失败率从 2.3% 降到 0.1%。\n"
             "下周计划：上线指标口径校验工具，"
             "覆盖 6 个核心业务域。")

    page.insert_textbox(fitz.Rect(50, 70, 320, 600), left, fontname="china-s", fontsize=10)
    page.insert_textbox(fitz.Rect(330, 70, 595, 600), right, fontname="china-s", fontsize=10)

    doc.save("twocol_sample.pdf")
    doc.close()
    print("生成 twocol_sample.pdf")


def make_scanned_memo():
    """扫描版会议纪要：文字渲染成图再合成 PDF，内容独有（验证 OCR 路径可检索性）。"""
    lines = [
        ("第三季度产品评审会会议纪要", 16),
        ("会议时间：2026 年 9 月 20 日 14:00", 12),
        ("地点：总部 3 楼会议室", 12),
        ("主持人：产品总监 王明", 12),
        ("参会：产品、研发、运营、市场各部门负责人", 12),
        ("", 12),
        ("一、智能客服项目", 14),
        ("智能客服项目验收通过，正式上线时间定为 10 月 15 日，上线前完成灰度测试。", 12),
        ("", 12),
        ("二、营销预算", 14),
        ("四季度营销预算追加 320 万元，其中线上投放 200 万元、线下活动 120 万元。", 12),
        ("", 12),
        ("三、人员配置", 14),
        ("研发部新增 12 名研发人员，需在 9 月 30 日前到岗，重点补充算法组。", 12),
        ("", 12),
        ("四、客户投诉率", 14),
        ("当前客户投诉率 3.8%，目标在四季度末降到 1.5%，由客服运营部牵头整改。", 12),
    ]
    lines2 = [
        ("五、后续安排", 14),
        ("下次评审会定于 10 月 10 日召开，各部门提前提交季度目标完成情况。", 12),
        ("", 12),
        ("会议纪要整理人：李雪", 12),
        ("2026 年 9 月 21 日", 12),
    ]

    def render_page(text_lines):
        tmp = fitz.open()
        p = tmp.new_page(width=595, height=842)
        y = 60
        for text, size in text_lines:
            if text:
                p.insert_text((60, y), text, fontname="china-s", fontsize=size)
            y += 34
        return tmp[0].get_pixmap(dpi=200)

    out = fitz.open()
    for text_lines in (lines, lines2):
        pix = render_page(text_lines)
        npage = out.new_page(width=595, height=842)
        npage.insert_image(npage.rect, stream=pix.tobytes("png"))
    out.save("scanned_memo.pdf")
    out.close()
    print("生成 scanned_memo.pdf")


if __name__ == "__main__":
    make_table_sample()
    make_scanned_sample()
    make_twocol_sample()
    make_scanned_memo()
