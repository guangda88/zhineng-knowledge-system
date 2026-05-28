#!/usr/bin/env python3
"""附录J：参考文献与推荐阅读"""
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml
import pickle

OUTPATH = "/home/ai/下载/未来医学相关/师资培训教材/第三册_医学气功与导引功法_师资培训教材.docx"
STATE = "/tmp/b3_progress.pkl"
doc = Document(OUTPATH)
with open(STATE,'rb') as f: total_chars = pickle.load(f)

def H(text, level=1):
    sz={0:22,1:18,2:16,3:14,4:13}[level]; fn={0:'黑体',1:'黑体',2:'黑体',3:'楷体',4:'楷体'}[level]
    p=doc.add_paragraph()
    if level<=2: p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    run=p.add_run(text); run.bold=True
    run.font.size=Pt(sz); run.font.name=fn
    run.element.rPr.rFonts.set(qn('w:eastAsia'),fn)
    p.paragraph_format.space_before=Pt({0:30,1:24,2:18,3:12,4:8}[level])
    p.paragraph_format.space_after=Pt({0:20,1:14,2:10,3:8,4:6}[level])
    if level==2: p.paragraph_format.page_break_before=True
    global total_chars; total_chars+=len(text)

def P(text):
    global total_chars; total_chars+=len(text)
    p=doc.add_paragraph()
    run=p.add_run(text); run.font.size=Pt(12); run.font.name='宋体'
    run.element.rPr.rFonts.set(qn('w:eastAsia'),'宋体')
    p.paragraph_format.first_line_indent=Cm(0.74); p.paragraph_format.line_spacing=1.5

def PB():
    p=doc.add_paragraph(); p.paragraph_format.first_line_indent=Cm(0)

def TBL(headers, rows, cw=None):
    global total_chars
    for r in rows: total_chars+=sum(len(str(v)) for v in r)
    table=doc.add_table(rows=1+len(rows), cols=len(headers))
    table.style='Table Grid'; table.alignment=WD_TABLE_ALIGNMENT.CENTER
    for i,h in enumerate(headers):
        c=table.rows[0].cells[i]; c.text=''
        p=c.paragraphs[0]; p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        r=p.add_run(h); r.bold=True; r.font.size=Pt(11)
        r.font.name='宋体'; r.element.rPr.rFonts.set(qn('w:eastAsia'),'宋体')
        c._tc.get_or_add_tcPr().append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="D9E2F3"/>'))
    for ri,rd in enumerate(rows):
        for ci,v in enumerate(rd):
            c=table.rows[ri+1].cells[ci]; c.text=''
            p=c.paragraphs[0]; p.alignment=WD_ALIGN_PARAGRAPH.CENTER
            r=p.add_run(str(v)); r.font.size=Pt(11)
            r.font.name='宋体'; r.element.rPr.rFonts.set(qn('w:eastAsia'),'宋体')
    if cw:
        for row in table.rows:
            for i,w in enumerate(cw):
                if i<len(row.cells): row.cells[i].width=Cm(w)
    PB()

# ======== 附录J ========
H('附录J  参考文献与推荐阅读', 2)
P('本附录列出了本教材编写过程中参考的主要文献和推荐带教老师阅读的专业书籍。参考文献分为中医经典、气功导引、现代研究、运动科学和教学方法五大类。带教老师在教学中遇到理论问题时，可以查阅相关参考文献获取更深入的知识。推荐阅读部分列出了适合不同水平带教老师阅读的专业书籍，供带教老师根据自己的水平和需求选择阅读。持续学习和知识更新是提高教学水平的重要途径，建议带教老师每年至少阅读两至三本相关专业书籍。')

H('J.1 中医经典文献', 3)

TBL(['序号', '书名', '作者/年代', '推荐章节', '阅读价值'], [
('1', '《黄帝内经·素问》', '战国至西汉', '"上古天真论""四气调神大论""生气通天论"', '中医养生理论的源头，理解天人合一、顺应四时的核心理念'),
('2', '《黄帝内经·灵枢》', '战国至西汉', '"经脉""经筋""本输"', '经络理论的经典论述，理解穴位和经络的运行规律'),
('3', '《难经》', '秦越人（扁鹊）', '"一难至二十四难"', '对《内经》的阐释和补充，深入理解脉学和脏腑理论'),
('4', '《伤寒杂病论》', '张仲景（东汉）', '"辨太阳病脉证并治"', '辨证论治的典范，理解中医诊断和治疗的基本思路'),
('5', '《针灸甲乙经》', '皇甫谧（晋代）', '"穴位定位""针灸方法"', '穴位定位的经典参考，是穴位按摩和导引的取穴依据'),
('6', '《千金要方》', '孙思邈（唐代）', '"养性""按摩""导引"', '养生和导引的集大成著作，包含丰富的功法练习方法'),
('7', '《本草纲目》', '李时珍（明代）', '"饮食养生""药食同源"', '药食同源的权威参考，理解饮食与健康的密切关系'),
('8', '《养生延命录》', '陶弘景（南朝梁）', '"导引按摩""呼吸吐纳"', '早期导引和呼吸训练的经典著作')
], [0.5,2.5,2,2.5,3.5])

H('J.2 气功导引专业文献', 3)

TBL(['序号', '书名', '作者/出版社', '核心内容', '推荐理由'], [
('1', '《中医气功学》', '全国高等中医药院校教材', '气功基础理论、功法分类、教学方法', '系统全面的气功教材，适合理论学习'),
('2', '《中医导引学》', '全国高等中医药院校教材', '导引的理论与方法，各类导引功法', '导引专业教材，理论深度高'),
('3', '《八段锦》', '国家体育总局编', '八段锦标准化动作和教学方法', '官方标准教材，动作规范权威'),
('4', '《简化太极拳》', '国家体育总局编', '二十四式简化太极拳标准教程', '太极拳入门的标准教材'),
('5', '《马王堆导引术》', '国家体育总局编', '马王堆导引术的复原和教学', '古法导引的现代复原，文化价值高'),
('6', '《五禽戏》', '国家体育总局编', '五禽戏标准动作和教学方法', '华佗五禽戏的现代标准化版本'),
('7', '《易筋经》', '国家体育总局编', '易筋经十二式标准教程', '传统少林功法的健身版'),
('8', '《气功疗法与养生》', '人民卫生出版社', '医学气功的临床应用与养生方法', '将气功与医学结合的实践指南'),
('9', '《站桩养生法》', '于永年著', '站桩功法的理论与实践', '站桩功法的权威著作，深入浅出'),
('10', '《太极拳全书》', '人民体育出版社', '太极拳各流派的完整介绍', '太极拳的百科全书式参考')
], [0.5,2.5,2,3,2.5])

H('J.3 现代科学研究文献', 3)

TBL(['序号', '研究方向', '代表性文献/期刊', '核心发现', '对教学的启示'], [
('1', '气功对自主神经的影响', 'Journal of Alternative and Complementary Medicine', '气功练习可激活副交感神经，降低交感神经活性', '解释气功缓解压力和焦虑的机制'),
('2', '八段锦对老年人平衡能力', '中国康复医学杂志, 2020', '12周八段锦练习显著改善老年人静态和动态平衡', '支持老年人练习八段锦预防跌倒'),
('3', '太极拳对心血管的影响', 'Journal of the American Geriatrics Society', '太极拳可降低血压、改善心脏功能', '支持心血管疾病患者的辅助康复'),
('4', '呼吸训练对失眠的影响', 'Sleep Medicine Reviews, 2019', '慢呼吸训练可改善睡眠质量和入睡时间', '支持呼吸训练用于失眠调理'),
('5', '站桩对骨密度的影响', '中国骨质疏松杂志, 2021', '长期站桩练习可减缓骨质流失', '支持中老年人通过站桩预防骨质疏松'),
('6', '气功对免疫功能的影响', 'International Journal of Psychophysiology', '气功练习可增强NK细胞活性和免疫球蛋白水平', '解释气功增强免疫力的科学机理'),
('7', '导引对慢性疼痛的影响', 'Pain Medicine, 2020', '导引功法可减轻慢性腰痛和颈痛', '支持功法用于慢性疼痛的辅助治疗'),
('8', '冥想对大脑的影响', 'Nature Reviews Neuroscience', '长期冥想可改变大脑结构和功能连接', '解释气功调心对认知功能的改善')
], [0.5,2.5,2.5,3,2.5])

H('J.4 运动科学与教学方法文献', 3)

TBL(['序号', '书名', '作者/出版社', '核心内容', '推荐理由'], [
('1', '《运动解剖学》', '全国体育院校教材', '人体肌肉骨骼系统的运动原理', '理解功法动作的解剖学基础'),
('2', '《运动生理学》', '全国体育院校教材', '运动对人体各系统的影响', '理解功法对身体的生理效应'),
('3', '《运动训练学》', '全国体育院校教材', '运动训练的原则和方法', '制定科学的功法训练方案'),
('4', '《运动损伤预防与康复》', '人民体育出版社', '运动损伤的预防和康复方法', '保障功法教学的安全性'),
('5', '《体育教学方法论》', '高等教育出版社', '体育教学的理论和方法', '提高功法教学的科学性和有效性'),
('6', '《成人教育学》', '教育科学出版社', '成人学习的特点和方法', '理解成人学员的学习特点'),
('7', '《运动心理学》', '全国体育院校教材', '运动对心理的影响和心理训练', '理解功法的心理调节作用'),
('8', '《急救与心肺复苏》', '红十字会教材', '急救知识和心肺复苏技能', '功法教学安全必备技能')
], [0.5,2.5,2,3,2.5])

H('J.5 推荐阅读书单（按等级）', 3)
P('以下是按带教老师等级推荐的阅读书单，带教老师可以根据自己的等级和水平选择阅读。初级带教老师建议重点阅读基础理论和功法教程类书籍，中级带教老师建议增加医学基础和教学方法类书籍，高级带教老师建议阅读科研文献和经典原著。每本书的推荐阅读时间和重点章节都有说明，帮助带教老师高效阅读。')

TBL(['等级', '书名', '预计阅读时间', '重点章节', '阅读目标'], [
('初级', '《八段锦》国家体育总局编', '1周', '全部', '掌握八段锦标准动作'),
('初级', '《简化太极拳》国家体育总局编', '2周', '全部', '掌握24式太极拳'),
('初级', '《中医气功学》教材', '2周', '第1-6章', '建立气功理论框架'),
('初级', '《急救与心肺复苏》', '1周', '全部', '掌握基本急救技能'),
('中级', '《中医导引学》教材', '3周', '第1-8章', '深入理解导引理论'),
('中级', '《运动解剖学》', '3周', '骨骼肌肉系统', '理解动作的解剖基础'),
('中级', '《运动生理学》', '3周', '心肺系统、神经系统', '理解功法的生理效应'),
('中级', '《体育教学方法论》', '2周', '教学方法、教学设计', '提高教学设计能力'),
('高级', '《黄帝内经·素问》', '1个月', '养生相关章节', '深入理解中医养生原理'),
('高级', '《千金要方》养生部分', '2周', '养性、按摩、导引', '学习古代导引方法'),
('高级', 'SCI论文精选（气功领域）', '持续', '最新研究', '跟踪科研前沿'),
('高级', '《运动训练学》', '3周', '训练原则、训练方法', '制定科学训练方案')
], [1,2.5,1.5,2.5,2.5])

doc.save(OUTPATH)
with open(STATE,'wb') as f: pickle.dump(total_chars, f)
print(f"Appendix J done, total chars: {total_chars}")
