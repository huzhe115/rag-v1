"""生成 v2 复杂 PDF 样本：真实规模（多页/大表格/跨页表/长文双栏/多页扫描件）。

用法：cd testsamples && python make_samples_v2.py
产物：table_v2.pdf / twocol_v2.pdf / scanned_memo_v2.pdf
"""
import fitz

HEADER = "XX 集团内部资料·未经许可不得外传"


def _footer(page, n, total):
    page.insert_text((50, 780), f"第 {n} 页 共 {total} 页", fontname="china-s", fontsize=9)


def make_table_v2():
    """3 页：12 行大表格（跨页，表头重复）+ 无线表格 + 结论段落 + 页眉页脚。"""
    doc = fitz.open()
    total = 3

    headers = ["事业部", "营收(万元)", "利润(万元)", "同比增速", "员工数"]
    rows = [
        ["云服务事业部", "8,520", "1,240", "+23.5%", "286"],      # 旧题 4 行保留
        ["数据智能事业部", "6,380", "890", "+12.1%", "174"],
        ["企业软件事业部", "4,150", "-320", "-8.3%", "152"],
        ["金融科技事业部", "9,760", "2,180", "+31.2%", "233"],
        ["物联网事业部", "3,870", "450", "+9.8%", "118"],
        ["智慧医疗事业部", "2,540", "180", "+6.4%", "96"],
        ["数字营销事业部", "5,620", "1,030", "+18.7%", "141"],
        ["供应链科技事业部", "4,890", "760", "+15.3%", "132"],
        ["汽车科技事业部", "7,340", "1,560", "+27.6%", "198"],
        ["教育科技事业部", "1,980", "-450", "-18.5%", "87"],
        ["游戏事业部", "6,910", "1,870", "+29.9%", "205"],
        ["海外业务事业部", "3,450", "520", "+11.4%", "104"],
    ]

    def draw_table(page, y0, sub_rows):
        col_w = [130, 90, 90, 80, 60]
        x0, row_h, n_rows = 50, 26, len(sub_rows) + 1
        tw = sum(col_w)
        for i in range(n_rows + 1):
            page.draw_line((x0, y0 + i * row_h), (x0 + tw, y0 + i * row_h))
        x = x0
        for w in col_w:
            page.draw_line((x, y0), (x, y0 + n_rows * row_h))
            x += w
        page.draw_line((x, y0), (x, y0 + n_rows * row_h))
        for ci, h in enumerate(headers):
            page.insert_text((x0 + 5 + sum(col_w[:ci]), y0 + 17), h, fontname="china-s", fontsize=10)
        for ri, row in enumerate(sub_rows):
            for ci, cell in enumerate(row):
                page.insert_text((x0 + 5 + sum(col_w[:ci]), y0 + (ri + 1) * row_h + 17),
                                 cell, fontname="china-s", fontsize=10)

    # 页 1：标题 + 导语 + 表头 + 前 6 行
    p1 = doc.new_page()
    p1.insert_text((50, 40), HEADER, fontname="china-s", fontsize=8)
    p1.insert_text((50, 60), "2026 年上半年部门业绩汇总表", fontname="china-s", fontsize=16)
    p1.insert_text((50, 90), "下表为集团十二个事业部上半年核心经营数据，数据来源：财务部季度报表。", fontname="china-s", fontsize=11)
    draw_table(p1, 120, rows[:6])
    _footer(p1, 1, total)

    # 页 2：表头重复 + 后 6 行（跨页表格）
    p2 = doc.new_page()
    p2.insert_text((50, 40), HEADER, fontname="china-s", fontsize=8)
    draw_table(p2, 80, rows[6:])
    _footer(p2, 2, total)

    # 页 3：结论 + 无线表格
    p3 = doc.new_page()
    p3.insert_text((50, 40), HEADER, fontname="china-s", fontsize=8)
    p3.insert_text((50, 60), "分析与结论", fontname="china-s", fontsize=16)
    p3.insert_text((50, 90), "上半年金融科技事业部增速最高，达到 31.2%；企业软件事业部出现亏损，"
                     "利润为 -320 万元，需要在下半年重点整改。", fontname="china-s", fontsize=11)
    p3.insert_text((50, 150), "各梯队利润率对比（无线表格）：", fontname="china-s", fontsize=11)
    borderless = [["梯队", "事业部数", "平均利润率"], ["第一梯队", "3", "18.4%"], ["第二梯队", "6", "9.2%"], ["第三梯队", "3", "-4.1%"]]
    y = 170
    for ri, row in enumerate(borderless):
        for ci, cell in enumerate(row):
            p3.insert_text((60 + ci * 120, y + ri * 24), cell, fontname="china-s", fontsize=10)
    _footer(p3, 3, total)

    doc.save("table_v2.pdf")
    doc.close()
    print("生成 table_v2.pdf")


def make_twocol_v2():
    """3 页双栏长文：每栏 300+ 字，跨页续栏，旧内容保留在前两栏。"""
    doc = fitz.open()
    total = 3

    columns = [
        # (左栏, 右栏) × 3 页
        ("【左栏·AI 平台组】\n本周完成向量检索服务升级，QPS 从 120 提升到 340，P99 延迟下降 42%。"
         "主要优化点是索引分片与查询缓存。\n下周计划：接入语义路由模块，预计可再降低 20% 的召回延迟。\n"
         "另外，向量模型的混合精度量化已完成灰度验证，显存占用下降 35%，单卡可承载的索引规模翻倍。"
         "团队正在评估多路召回与蒸馏小模型的组合方案，目标是在双十一大促前把平均延迟压到 80ms 以内。",
         "【右栏·数据平台组】\n数据同步链路新增断点续传能力，凌晨批处理任务失败率从 2.3% 降到 0.1%。\n"
         "下周计划：上线指标口径校验工具，覆盖 6 个核心业务域。\n"
         "实时数仓的秒级延迟链路已稳定运行两周，日均处理消息量 45 亿条，"
         "峰值时段端到端延迟中位数为 1.8 秒，长尾 99 分位为 4.2 秒，均满足业务 SLA 要求。"),
        ("【左栏·前端架构组】\n微前端基座完成灰度发布，首屏加载时间从 2.8 秒优化到 1.1 秒，"
         "包体积下降 47%。子应用独立部署机制已接入 12 个业务模块，"
         "灰度期间的线上错误率保持在 0.03% 以下，优于 0.1% 的既定目标。\n"
         "组件库覆盖率本周提升到 86%，剩余未覆盖的 23 个页面已排期在两周内完成迁移。",
         "【右栏·服务端架构组】\n网关层完成限流熔断升级，大促压测中扛住了 28 万 QPS 的峰值流量，"
         "超时率控制在 0.02%。链路追踪采样率从 5% 提升到 30%，慢查询定位时间缩短一半。\n"
         "缓存中间件的集群扩容已完成，命中率从 91% 提升到 96%，数据库压力下降约 40%，"
         "预计每月可节省云资源成本 15 万元。"),
        ("【左栏·质量保障组】\n自动化测试用例数突破 2 万条，核心链路覆盖率 94%。"
         "流水线并行改造后，全量回归耗时从 46 分钟缩短到 21 分钟，提测等待时间明显下降。\n"
         "混沌工程平台完成二期建设，新增网络延迟与磁盘故障注入能力，"
         "本月已支撑 6 次容灾演练，发现并修复 3 个单点隐患。",
         "【右栏·安全合规组】\n完成等保三级复测准备，渗透测试发现的高危漏洞已全部修复。"
         "数据脱敏平台接入 31 个业务系统，日均处理敏感字段 8 亿条。\n"
         "本月新增告警降噪规则 120 条，安全告警有效率从 28% 提升到 61%，"
         "值班同学的告警疲劳问题得到明显缓解。"),
    ]

    for page_no in range(total):
        page = doc.new_page()
        page.insert_text((50, 40), f"技术周报（双栏样例）第 {page_no + 1} 期", fontname="china-s", fontsize=14)
        left, right = columns[page_no]
        page.insert_textbox(fitz.Rect(50, 70, 320, 750), left, fontname="china-s", fontsize=10)
        page.insert_textbox(fitz.Rect(330, 70, 595, 750), right, fontname="china-s", fontsize=10)
        _footer(page, page_no + 1, total)

    doc.save("twocol_v2.pdf")
    doc.close()
    print("生成 twocol_v2.pdf")


def make_scanned_memo_v2():
    """4 页扫描版会议纪要：旧内容保留，新增产品路线图与风险预案章节。"""
    pages = [
        [("第三季度产品评审会会议纪要", 16),
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
         ("研发部新增 12 名研发人员，需在 9 月 30 日前到岗，重点补充算法组。", 12)],
        [("四、客户投诉率", 14),
         ("当前客户投诉率 3.8%，目标在四季度末降到 1.5%，由客服运营部牵头整改。", 12),
         ("", 12),
         ("五、后续安排", 14),
         ("下次评审会定于 10 月 10 日召开，各部门提前提交季度目标完成情况。", 12),
         ("", 12),
         ("六、产品路线图", 14),
         ("智能客服二期将接入多轮对话与情绪识别能力，计划 12 月底上线。", 12),
         ("推荐系统重构项目进入开发冲刺阶段，目标在 11 月 15 日完成联调。", 12),
         ("数据中台指标服务计划新增 45 个核心指标，覆盖财务与供应链两个域。", 12),
         ("", 12),
         ("七、风险与预案", 14),
         ("灰度期间若智能客服满意度低于 85%，则回滚至人工客服为主模式。", 12),
         ("营销预算执行偏差超过 10% 时，需重新提交预算审批。", 12)],
        [("八、资源协调", 14),
         ("GPU 训练资源优先级向推荐系统项目倾斜，每周配额 120 卡时。", 12),
         ("客服外包团队在 10 月 8 日前完成 40 人扩编，培训考核合格率要求 95% 以上。", 12),
         ("", 12),
         ("九、数据合规", 14),
         ("用户行为数据用于模型训练前必须完成匿名化处理，并通过合规评审。", 12),
         ("客户投诉数据留存期限为 24 个月，到期自动归档销毁。", 12),
         ("", 12),
         ("十、会议决议汇总", 14),
         ("本次会议共形成 7 项决议，全部获得一致通过，会后由产品部发布决议跟踪表。", 12)],
        [("会议纪要整理人：李雪", 12),
         ("2026 年 9 月 21 日", 12),
         ("", 12),
         ("附录：决议跟踪表编号说明", 12),
         ("决议编号格式为 D-2026-序号，跟踪表每周五更新一次进度状态。", 12),
         ("逾期未完成的决议将自动升级至产品委员会评审。", 12)],
    ]

    out = fitz.open()
    for text_lines in pages:
        tmp = fitz.open()
        p = tmp.new_page(width=595, height=842)
        y = 60
        for text, size in text_lines:
            if text:
                p.insert_text((60, y), text, fontname="china-s", fontsize=size)
            y += 40
        pix = tmp[0].get_pixmap(dpi=200)
        npage = out.new_page(width=595, height=842)
        npage.insert_image(npage.rect, stream=pix.tobytes("png"))
        tmp.close()
    out.save("scanned_memo_v2.pdf")
    out.close()
    print("生成 scanned_memo_v2.pdf")


if __name__ == "__main__":
    make_table_v2()
    make_twocol_v2()
    make_scanned_memo_v2()
