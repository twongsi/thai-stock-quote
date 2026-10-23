# ทบทวนวรรณกรรม: ความแม่นยำและมูลค่าเชิงการลงทุนของราคาเป้าหมาย คำแนะนำ และประมาณการ EPS ของนักวิเคราะห์ (เน้นตลาดเกิดใหม่และ SET)

> จัดทำ: ตุลาคม 2026 · ทุกงานที่อ้างอิงในเอกสารนี้ค้นและตรวจสอบเมตาดาทา (ผู้แต่ง ปี วารสาร DOI) ผ่านฐานข้อมูล Scite, Consensus และ Wiley Scholar Gateway แล้ว ตัวเลขที่ยกมานำมาจากบทคัดย่อ ข้อความฉบับเต็มที่เปิดอ่านได้ หรือข้อความอ้างอิงในงานที่อ้างถึงงานนั้น (citation snippet) ซึ่งระบุไว้ในจุดที่ใช้ งานที่เป็นสารนิพนธ์ (independent study) ของจุฬาลงกรณ์มหาวิทยาลัยยังไม่ผ่านการประเมินโดยผู้ทรงคุณวุฒิ จึงควรถือเป็นหลักฐานเบื้องต้นเท่านั้น

## 1. บทนำ

นักวิเคราะห์ฝั่งขาย (sell-side analysts) ให้ข้อมูลหลักสามอย่าง คือ ประมาณการกำไรต่อหุ้น (EPS) คำแนะนำซื้อ/ถือ/ขาย และราคาเป้าหมาย (target price, TP) ในตลาดไทย ค่าเฉลี่ยของข้อมูลเหล่านี้ หรือ "consensus" (เช่น จาก IAA หรือเว็บรวบรวมข้อมูลอย่าง 9hoon/aset ที่ `consensus.py` ใน repo นี้ดึงมา) มักถูกนำมาคำนวณเป็น **upside** = TP / ราคาปัจจุบัน − 1 แล้วใช้คัดหุ้น เอกสารนี้สรุปหลักฐานเชิงประจักษ์ใน 4 ประเด็น ได้แก่ (1) ความแม่นยำและความมองโลกในแง่ดีเกินจริง (optimism bias) ของราคาเป้าหมาย (2) มูลค่าเชิงการลงทุนของคำแนะนำและการปรับ consensus (3) พฤติกรรมไหลตามกัน (herding) และการกระจายตัวของประมาณการ (dispersion) และ (4) หลักฐานจากตลาดเกิดใหม่ เอเชีย และไทย จากนั้นสรุปข้อควรปฏิบัติสำหรับ screener ใน repo นี้ ซึ่งใช้ได้ทั้งในงาน private banking และการสอน

## 2. ความแม่นยำของราคาเป้าหมายและ optimism bias

**ราคาเป้าหมายสูงกว่าราคาตลาดอย่างเป็นระบบ** Brav and Lehavy (2003) พบว่าตลาดตอบสนองต่อการปรับราคาเป้าหมายอย่างมีนัยสำคัญ แม้ควบคุมการปรับคำแนะนำและ EPS ที่ออกพร้อมกันแล้ว แต่โดยเฉลี่ยราคาเป้าหมาย 1 ปีสูงกว่าราคาปัจจุบันถึง 28% (ข้อมูลสหรัฐฯ ปี 1997–1999) Asquith et al. (2005) วิเคราะห์เนื้อหารายงานของนักวิเคราะห์ All-American ทั้งฉบับ และพบว่าราคาเป้าหมายกับเหตุผลประกอบเป็นองค์ประกอบเดียวที่มีนัยสำคัญเมื่อนักวิเคราะห์ยืนยันคำแนะนำเดิม (reiteration) ทั้งยังไม่พบความสัมพันธ์ระหว่างวิธีประเมินมูลค่าที่ใช้กับความแม่นยำ

**อัตราการบรรลุราคาเป้าหมายต่ำ** Bradshaw et al. (2013) ศึกษาราคาเป้าหมาย 12 เดือนของสหรัฐฯ ปี 2000–2009 พบว่า ผลตอบแทนที่ราคาเป้าหมายบอกเป็นนัย (implied return) สูงกว่าผลตอบแทนจริงเฉลี่ย 15% ค่าคลาดเคลื่อนสัมบูรณ์เฉลี่ย 45% ราคาเป้าหมายบรรลุเพียง **38% ณ สิ้นงวด** แต่บรรลุ **64% ณ จุดใดจุดหนึ่งระหว่างงวด** หลักฐานว่านักวิเคราะห์บางคนเก่งกว่าคนอื่นอย่างสม่ำเสมอมีนัยสำคัญทางสถิติ แต่อ่อนในเชิงเศรษฐกิจ (ตัวเลขจากบทคัดย่อฉบับ working paper บน SSRN) ในตลาดอิตาลี Bonini et al. (2010) รายงานอัตราบรรลุที่ต่ำกว่านั้นอีก คือ 33.12% (ณ จุดใดก็ได้) และ 20.0% (ณ สิ้นงวด) ผลตอบแทนที่บอกเป็นนัยยิ่งสูง ความแม่นยำยิ่งต่ำ ("a large part of every target price forecast is systematically not met") Bilinski et al. (2013) สรุปงานนี้ว่า ความคลาดเคลื่อนจะสูงขึ้นในหุ้นที่ราคาเป้าหมายคาดการณ์ราคาขึ้นแรง หุ้นขนาดใหญ่ หุ้นที่ขาดทุน และหุ้นที่มี momentum สูง

**สถาบันของประเทศมีผล** Bilinski et al. (2013) ศึกษา 16 ประเทศและพบว่านักวิเคราะห์มีความสามารถในการตั้งราคาเป้าหมายแม่นยำที่แตกต่างกันและคงอยู่ต่อเนื่อง นักวิเคราะห์ที่แม่นในอดีต มีประสบการณ์ ทำงานในโบรกเกอร์ใหญ่ และเชี่ยวชาญเฉพาะประเทศ ตั้งราคาเป้าหมายได้แม่นกว่า คุณภาพการเปิดเผยข้อมูล ระบบกฎหมาย และ IFRS อธิบายความแตกต่างระหว่างประเทศได้ Bradshaw et al. (2019) พบว่านักวิเคราะห์ที่อยู่ในประเทศที่มีโครงสร้างสถาบันเข้มแข็งตั้งราคาเป้าหมายมองโลกในแง่ดีน้อยกว่า และราคาเป้าหมายมีความหมายต่อมูลค่ามากกว่า ฉบับ working paper (Bradshaw et al., 2012; นักวิเคราะห์ 11,633 คน ใน 44 ประเทศ) ระบุว่า optimism สัมพันธ์เชิงบวกกับผลประโยชน์ทับซ้อน และสัมพันธ์เชิงลบกับการคุ้มครองนักลงทุนและการบังคับใช้กฎหมาย

**ส่วนใดของ upside ที่มีข้อมูลจริง** Dechow and You (2020) แยก implied return ออกเป็นส่วนที่มาจากผลตอบแทนในอนาคต ความผิดพลาดในการพยากรณ์ปัจจัยพื้นฐาน ความผิดพลาดในการประมาณผลตอบแทนที่คาดหวังต่อความเสี่ยง และอคติจากแรงจูงใจ พบว่าปัจจัยเหล่านี้อธิบายความแปรปรวนข้ามหุ้นได้ราวหนึ่งในสี่ และนักลงทุนไม่ได้หักอคติที่คาดการณ์ได้ออกอย่างสมบูรณ์ ฉบับ SSRN รายงานว่า implied return ของ consensus "ดิบ" ไม่สัมพันธ์อย่างมีนัยสำคัญกับผลตอบแทนในอนาคต แต่ส่วนที่ "กรองอคติแล้ว" (purified) สัมพันธ์อย่างมีนัยสำคัญ กลยุทธ์ long–short ตาม decile ของส่วนนี้ให้ผลตอบแทนปรับความเสี่ยงราว 0.89–1.14% ในเดือนถัดไป ส่วน Da and Schaumburg (2011) ชี้ว่าการจัดอันดับ upside **ภายในอุตสาหกรรมเดียวกัน** มีอำนาจพยากรณ์ผลตอบแทนระยะสั้น (ตามที่ Dechow & You อธิบายงานนี้)

## 3. มูลค่าเชิงการลงทุนของคำแนะนำและการปรับ consensus

Womack (1996) พบว่าราคาปรับตัวทันทีเมื่อมีคำแนะนำใหม่ แต่ปรับไม่ครบ หลังคำแนะนำซื้อราคาไหลต่อ (drift) เฉลี่ย +2.4% เป็นช่วงสั้น ขณะที่หลังคำแนะนำขาย drift −9.1% และยาวถึงหกเดือน Barber et al. (2001) พบว่าการซื้อหุ้นที่ consensus ดีที่สุดและขายชอร์ตหุ้นที่แย่ที่สุด โดยปรับพอร์ตรายวัน ให้ผลตอบแทนส่วนเกินขั้นต้นมากกว่า 4% ต่อปี แต่ต้องซื้อขายบ่อยมาก **หลังหักต้นทุนธุรกรรม ผลตอบแทนสุทธิไม่มากกว่าศูนย์อย่างน่าเชื่อถือ** ถ้าปรับพอร์ตช้าลง ผลตอบแทนลดลง แต่ฝั่งหุ้นที่ได้คำแนะนำแย่ที่สุดยังมีนัยสำคัญ

Jegadeesh et al. (2004) เป็นงานที่เกี่ยวข้องกับ screener มากที่สุด นักวิเคราะห์มักแนะนำหุ้น "glamour" (momentum บวก โตเร็ว ซื้อขายมาก และแพง) **ระดับ** ของ consensus เพิ่มมูลค่าได้เฉพาะในหุ้นที่มีลักษณะเชิงปริมาณดี (หุ้นคุณค่าและ momentum บวก) ส่วนในหุ้นที่มีลักษณะไม่ดี consensus ที่สูงกว่ากลับตามมาด้วยผลตอบแทนที่แย่กว่า ในทางกลับกัน **การเปลี่ยนแปลง** ของ consensus รายไตรมาสพยากรณ์ผลตอบแทนได้อย่างมั่นคง และมีข้อมูลที่ไม่ซ้ำกับตัวแปรอื่น

สำหรับประมาณการ EPS นั้น Loh and Mian (2006) พบว่านักวิเคราะห์ที่ประมาณการ EPS แม่นกว่าให้คำแนะนำที่ทำกำไรได้มากกว่า Bradshaw (2004) พบว่าคำแนะนำสัมพันธ์กับวิธีประเมินแบบ heuristic (PEG และการเติบโตระยะยาว) มากกว่าแบบมูลค่าปัจจุบัน นักลงทุนแบบซื้อแล้วถือจะได้ผลตอบแทนสูงกว่าถ้าใช้แบบจำลองมูลค่าปัจจุบันที่ป้อน EPS ของนักวิเคราะห์ แทนการทำตามคำแนะนำ

## 4. Herding และการกระจายตัวของ consensus

Welch (2000) พบว่านักวิเคราะห์มีแนวโน้มปรับคำแนะนำเข้าหา consensus เดิมมากกว่าออกห่าง (ตามที่ Jegadeesh & Kim สรุป) Hong et al. (2000) พบว่านักวิเคราะห์อายุงานน้อยออกประมาณการห่างจาก consensus น้อยกว่า ซึ่งสอดคล้องกับแบบจำลองว่าความกังวลเรื่องอาชีพทำให้เกิด herding Graham (1999) แสดงในเชิงทฤษฎีและเชิงประจักษ์ว่าผู้มีชื่อเสียงสูงหรือความสามารถต่ำมีแนวโน้ม herd Clement and Tse (2005) พบว่าประมาณการที่ "กล้า" (bold) แม่นกว่าประมาณการที่ herd และสะท้อนข้อมูลส่วนตัวได้ครบกว่า Jegadeesh and Kim (2010) พบว่าราคาตอบสนองแรงกว่าเมื่อคำแนะนำใหม่ออกห่างจาก consensus ซึ่งหมายความว่าตลาดรู้ว่านักวิเคราะห์ herd และนักวิเคราะห์จากโบรกเกอร์ใหญ่ หรือที่ติดตามหุ้นที่ dispersion ต่ำ herd มากกว่า Huang et al. (2017) ประมาณว่าราว 60% ของนักวิเคราะห์ herd เข้าหา consensus

สำหรับ dispersion นั้น Diether et al. (2002) พบว่าหุ้นในกลุ่ม dispersion ของ EPS สูงสุดให้ผลตอบแทนต่ำกว่ากลุ่มต่ำสุด 9.48% ต่อปี ผลชัดที่สุดในหุ้นเล็กและหุ้นที่ราคาตกในปีที่ผ่านมา และสอดคล้องกับคำอธิบายแบบ "ความเห็นต่าง + ข้อจำกัดการขายชอร์ต" มากกว่าคำอธิบายแบบความเสี่ยง Johnson (2004) เสนอคำอธิบายทางเลือกว่า dispersion เป็นตัวแทนของความเสี่ยงด้านข้อมูลที่ไม่ถูกตั้งราคา หลักฐานจากเอเชียไม่ไปทางเดียวกัน Chae and Kim (2026) พบว่าใน KOSPI/KOSDAQ dispersion ของ**ราคาเป้าหมาย**สัมพันธ์เชิง**บวก**กับผลตอบแทนเดือนถัดไป

## 5. หลักฐานจากตลาดเกิดใหม่ เอเชีย และไทย

**ตลาดเกิดใหม่โดยรวม** Moshirian et al. (2009) ศึกษา 13 ตลาดเกิดใหม่ ปี 1996–2005 ยืนยันว่าคำแนะนำมีอคติเชิงบวก (Bradshaw et al., 2019 สรุปไว้) และพบว่าคำแนะนำมีผลต่อราคาอย่างมีนัยสำคัญ มี post-recommendation drift ราว 4–6 สัปดาห์ (ตามที่ Sharda, 2021 สรุปไว้) Lai and Teo (2008) พบว่าในตลาดเกิดใหม่ นักวิเคราะห์ท้องถิ่นให้คำแนะนำมองโลกในแง่ดีกว่านักวิเคราะห์ต่างชาติอย่างเป็นระบบ ("home bias") อคตินี้มากกว่าข้อได้เปรียบด้านข้อมูลของคนท้องถิ่น การปรับขึ้นของนักวิเคราะห์ท้องถิ่นจึงให้ผลด้อยกว่า และอคตินี้โยงกับแรงกดดันจากวาณิชธนกิจ Chan and Hameed (2006) พบว่าในตลาดเกิดใหม่ นักวิเคราะห์ผลิตข้อมูลระดับตลาดมากกว่าข้อมูลเฉพาะบริษัท ยิ่งมีนักวิเคราะห์ติดตามมาก ราคาหุ้นยิ่งเคลื่อนไหวไปพร้อมตลาด (synchronicity) มากขึ้น

**เอเชียและอาเซียน** Coën and Desfleurs (2004) ศึกษา 8 ตลาดแปซิฟิก ปี 1990–2000 พบว่าประมาณการ EPS สูงเกินจริงอย่างเป็นระบบทั้งก่อนและหลังวิกฤต 1997 Loh and Mian (2003) พบว่าในสิงคโปร์ หลังวิกฤตเอเชียเริ่ม ประมาณการกลายเป็นสูงเกินจริงและปรับรับข่าวร้ายไม่ครบ ขณะที่ Black and Carnes (2006) ซึ่งศึกษา 13 เศรษฐกิจในเอเชียแปซิฟิกกลับพบ**อคติเชิงลบ**โดยเฉลี่ย และพบว่าประเทศที่เปิดกว้างและแข่งขันได้สูงมีประมาณการแม่นกว่า ทิศทางของอคติ EPS จึงขึ้นกับช่วงเวลาและนิยามที่ใช้ Choi et al. (2021) ศึกษาประมาณการ EPS 7 ตลาดเอเชียรวม **ไทย** (ตัวอย่างไทย 69,259 ประมาณการ ปี 1994–2016) พบว่านักวิเคราะห์ท้องถิ่นที่ "กล้า" แม่นที่สุด ส่วนนักวิเคราะห์ท้องถิ่นที่ herd แม่นน้อยที่สุดกลุ่มหนึ่ง Sayed (2017) วิเคราะห์รายงาน 502 ฉบับใน 7 ตลาดเอเชียรวมไทย (ตั้งแต่ปี 2008) พบว่านักวิเคราะห์นิยมใช้ P/E โดยเฉพาะช่วงหลังวิกฤต 2008 และราคาเป้าหมายจาก P/E แม่นกว่าจาก DCF เพียงเล็กน้อย

**ไทย (SET)** ยังไม่พบบทความในวารสารระดับนานาชาติที่วัดอัตราบรรลุราคาเป้าหมายใน SET โดยตรง หลักฐานที่มีส่วนใหญ่เป็นสารนิพนธ์ของจุฬาลงกรณ์มหาวิทยาลัย
- Schmidt (2020) ศึกษาตลาดไทยปี 2005–2017 พบ optimism ในประมาณการเกินจริง โดยเฉพาะโบรกเกอร์/ธนาคารที่มีกองทุนรวมในเครือถือหุ้นบริษัทที่ตนวิเคราะห์ และธนาคารที่เป็นผู้จัดจำหน่ายหลักในช่วง IPO ซึ่ง optimism จะลดลงสู่ระดับเฉลี่ยราวหนึ่งปีหลังเสนอขาย
- Kromadit (2021) ศึกษาปี 2019–2021 พบว่าการปรับขึ้นคำแนะนำและราคาเป้าหมายตามมาด้วย AAR/ACAR เป็นบวกอย่างมีนัยสำคัญ ส่วนการปรับลงตามมาด้วยค่าเป็นลบ แสดงว่าข่าวการปรับมีเนื้อหาข้อมูล
- Chirabandhu (2019) พบว่ากลยุทธ์ซื้อหุ้นที่ target-price expected return (TPER) สูง ชนะกลยุทธ์ P/E ในเดือนแรกหลังข้อมูลออก และยังให้ผลตอบแทนส่วนเกินหลังควบคุมขนาด คุณค่า และสภาพคล่อง
- Petkajee (2020) ใช้ consensus EPS ของหุ้น SET พบว่าความคลาดเคลื่อนของประมาณการมีความต่อเนื่อง (นักวิเคราะห์เรียนรู้จากความผิดพลาดเดิม) ในแบบจำลองที่สอง จำนวนนักวิเคราะห์ ความแปรปรวนของ target return และสัดส่วนคำแนะนำ "ซื้อ" สัมพันธ์กับความคลาดเคลื่อน แต่ผลนี้ไม่คงทนเมื่อตัดค่าผิดปกติออก

ไม่พบงานวิชาการที่ประเมินความแม่นยำของ consensus EPS จาก IAA Survey โดยตรง

## 6. ตารางสรุปผลการศึกษาสำคัญ

| Study | Market/Period | Finding |
|---|---|---|
| Womack (1996) | สหรัฐฯ, 14 โบรกเกอร์ใหญ่ | drift หลังคำแนะนำซื้อ +2.4% (สั้น) หลังคำแนะนำขาย −9.1% (6 เดือน) |
| Barber et al. (2001) | สหรัฐฯ, consensus | ผลตอบแทนส่วนเกินขั้นต้น >4%/ปี แต่ผลตอบแทนสุทธิหลังต้นทุนไม่มากกว่าศูนย์อย่างน่าเชื่อถือ |
| Diether et al. (2002) | สหรัฐฯ | dispersion ของ EPS สูง → ผลตอบแทนต่ำกว่า 9.48%/ปี (quintile สูงสุดเทียบต่ำสุด) |
| Brav & Lehavy (2003) | สหรัฐฯ 1997–1999 | TP สูงกว่าราคา 28% โดยเฉลี่ย, การปรับ TP มีเนื้อหาข้อมูล |
| Jegadeesh et al. (2004) | สหรัฐฯ | ระดับ consensus เพิ่มมูลค่าเฉพาะในหุ้นคุณค่า/momentum บวก, การเปลี่ยนแปลงของ consensus พยากรณ์ผลตอบแทนได้ |
| Asquith et al. (2005) | สหรัฐฯ, รายงาน All-American | TP และเหตุผลประกอบสำคัญที่สุดเมื่อยืนยันคำแนะนำเดิม, วิธีประเมินไม่สัมพันธ์กับความแม่นยำ |
| Clement & Tse (2005) | สหรัฐฯ | ประมาณการ bold แม่นกว่าประมาณการที่ herd |
| Chan & Hameed (2006) | ตลาดเกิดใหม่ | ยิ่งมีนักวิเคราะห์ติดตามมาก synchronicity ยิ่งสูง (ผลิตข้อมูลระดับตลาด) |
| Lai & Teo (2008) | ตลาดเกิดใหม่ | นักวิเคราะห์ท้องถิ่นมองโลกในแง่ดีกว่าต่างชาติ, การปรับขึ้นของคนท้องถิ่นให้ผลด้อยกว่า |
| Moshirian et al. (2009) | 13 ตลาดเกิดใหม่, 1996–2005 | คำแนะนำมีอคติเชิงบวกแต่มีผลต่อราคา, มี drift |
| Bonini et al. (2010) | อิตาลี | TP บรรลุ 33.1% (ณ จุดใดก็ได้) / 20.0% (สิ้นงวด) |
| Jegadeesh & Kim (2010) | สหรัฐฯ | นักวิเคราะห์ herd, ตลาดตอบสนองแรงกว่าต่อการปรับที่ออกห่าง consensus |
| Da & Schaumburg (2011) | สหรัฐฯ | upside ที่จัดอันดับภายในอุตสาหกรรมพยากรณ์ผลตอบแทนระยะสั้นได้ |
| Bilinski et al. (2013) | 16 ประเทศ | ความแม่นยำของ TP แตกต่างกันอย่างต่อเนื่องระหว่างนักวิเคราะห์, สถาบันของประเทศมีผล |
| Bradshaw et al. (2013) | สหรัฐฯ 2000–2009 | TP บรรลุ 38% (สิ้นงวด) / 64% (ระหว่างงวด), ค่าคลาดเคลื่อนสัมบูรณ์ 45% |
| Sayed (2017) | 7 ตลาดเอเชียรวมไทย, 2008– | P/E ถูกใช้มากกว่าและแม่นกว่า DCF เล็กน้อย |
| Bradshaw et al. (2019) | 44 ประเทศ | สถาบันที่เข้มแข็ง → TP optimism ต่ำลง และ TP มีความหมายต่อมูลค่ามากขึ้น |
| Dechow & You (2020) | สหรัฐฯ | implied return มีอคติที่คาดการณ์ได้, ส่วนที่กรองอคติแล้วพยากรณ์ผลตอบแทนได้ดีกว่า |
| Choi et al. (2021) | 7 ตลาดเอเชียรวมไทย, 1994–2016 | นักวิเคราะห์ท้องถิ่นที่ bold แม่นที่สุด, คนท้องถิ่นที่ herd แม่นน้อยที่สุด |
| Schmidt (2020)* | ไทย 2005–2017 | optimism สูงในโบรกเกอร์ที่มีกองทุนในเครือและผู้จัดจำหน่ายหลัก IPO |
| Kromadit (2021)* | ไทย 2019–2021 | การปรับขึ้น/ลงของคำแนะนำและ TP → AAR/ACAR บวก/ลบอย่างมีนัยสำคัญ |
| Chirabandhu (2019)* | ไทย | กลยุทธ์ TPER สูงให้ผลตอบแทนส่วนเกินในเดือนแรก หลังควบคุม size, value และ liquidity |

\* สารนิพนธ์ จุฬาลงกรณ์มหาวิทยาลัย ยังไม่ผ่านการประเมินโดยผู้ทรงคุณวุฒิ

## 7. ข้อสรุปสำหรับ screener ใน repo นี้

ปัจจุบัน `analytics.screen()` รวม z-score ของ `Upside` (น้ำหนัก 0.20) เข้ากับ momentum 12-1 (0.35), ความผันผวนต่ำ (−0.25) และ dividend yield (0.20) โดย `Upside` มาจาก snapshot ล่าสุดของ `consensus.py` จากหลักฐานข้างต้น ควรอ่านและปรับดังนี้

1. **อย่าตีความ upside เป็นผลตอบแทนที่คาดหวัง** ราคาเป้าหมายบรรลุ ณ สิ้นงวดเพียงราว 20–38% และ implied return สูงกว่าผลตอบแทนจริงเฉลี่ยราว 15 จุด (Bonini et al., 2010; Bradshaw et al., 2013) เมื่อสื่อสารกับลูกค้า private banking ควรใช้ upside เป็น**ตัวจัดอันดับ** ไม่ใช่ตัวเลขผลตอบแทนที่สัญญาได้
2. **ใช้ upside เทียบภายในอุตสาหกรรม** Da and Schaumburg (2011) และ Dechow and You (2020) ชี้ว่าข้อมูลอยู่ใน upside เชิงเปรียบเทียบ หรือส่วนที่ปรับอคติแล้ว ข้อเสนอคือ demean ตาม sector ของ SET ก่อนทำ z-score และตัดค่าสุดขั้ว (winsorize) เพราะ upside ที่สูงมากสัมพันธ์กับความคลาดเคลื่อนสูง
3. **เพิ่มตัวแปร "การเปลี่ยนแปลง" ของ consensus** การเปลี่ยนแปลงของ consensus มีพลังพยากรณ์มั่นคงกว่าระดับ (Jegadeesh et al., 2004) และตลาดไทยตอบสนองต่อการปรับขึ้น/ลงของ TP และคำแนะนำ (Kromadit, 2021) repo นี้เก็บ snapshot รายวันใน `data/consensus/YYYY-MM-DD.csv` อยู่แล้ว จึงคำนวณ ΔTP หรือ Δ%Buy รายเดือน/ไตรมาสได้ทันที
4. **การรวมกับ momentum มีเหตุผลรองรับ** consensus ช่วยได้เฉพาะในหุ้นที่มีลักษณะเชิงปริมาณดี (Jegadeesh et al., 2004) แนวทางหนึ่งคือใช้ upside เป็นตัวกรองรองในกลุ่มที่ momentum บวกแล้ว แทนการบวกคะแนนเชิงเส้น
5. **ถ่วงน้ำหนักด้วยจำนวนนักวิเคราะห์และ dispersion** หุ้นที่มีนักวิเคราะห์น้อยมี consensus ที่ขึ้นกับคนคนเดียว ส่วน dispersion สูงสัมพันธ์กับผลตอบแทนในอนาคตที่ต่ำกว่าในสหรัฐฯ (Diether et al., 2002) แต่ในเกาหลีพบความสัมพันธ์เชิงบวก (Chae & Kim, 2026) จึงควรใช้ dispersion เป็นตัวกรองหรือลดน้ำหนักความเชื่อมั่น และทดสอบกับข้อมูลไทยก่อนกำหนดทิศทาง
6. **ระวังอคติเชิงสถาบันของไทย** optimism สัมพันธ์กับผลประโยชน์ทับซ้อน เช่น กองทุนในเครือและการจัดจำหน่าย IPO (Schmidt, 2020; Lai & Teo, 2008) และสัมพันธ์กับความเข้มแข็งของสถาบัน (Bradshaw et al., 2019) หุ้นที่เพิ่ง IPO หรือเพิ่มทุนควรตั้งน้ำหนัก upside ต่ำลง
7. **ต้นทุนธุรกรรมและการทดสอบย้อนหลัง** ผลตอบแทนจาก consensus อาจหายไปหลังหักต้นทุน (Barber et al., 2001) ปัจจุบัน `backtest()` ทดสอบเฉพาะ momentum (ต้นทุน 20 bps) เพราะยังไม่มี consensus ย้อนหลัง ควรสะสม snapshot อย่างน้อย 12–24 เดือนก่อนอ้างว่าปัจจัย upside "ใช้ได้" ใน SET และระวัง look-ahead bias จากวันที่ข้อมูลเผยแพร่จริง
8. **สำหรับการสอน** ใช้ screener นี้สาธิตได้สามบทเรียน คือ (ก) ความต่างระหว่าง "ข้อมูลมีเนื้อหา" (ตลาดตอบสนอง) กับ "กลยุทธ์ทำกำไรหลังต้นทุน" (ข) อคติเชิงแรงจูงใจและ herding และ (ค) ปัญหาการสรุปผลจากงานในสหรัฐฯ มาใช้กับตลาดเกิดใหม่ ที่หลักฐานในไทยยังจำกัดและส่วนใหญ่ยังไม่ผ่านการประเมินโดยผู้ทรงคุณวุฒิ

## เอกสารอ้างอิง (APA 7)

Asquith, P., Mikhail, M. B., & Au, A. S. (2005). Information content of equity analyst reports. *Journal of Financial Economics, 75*(2), 245–282. https://doi.org/10.1016/j.jfineco.2004.01.002

Barber, B., Lehavy, R., McNichols, M., & Trueman, B. (2001). Can investors profit from the prophets? Security analyst recommendations and stock returns. *The Journal of Finance, 56*(2), 531–563. https://doi.org/10.1111/0022-1082.00336

Bilinski, P., Lyssimachou, D., & Walker, M. (2013). Target price accuracy: International evidence. *The Accounting Review, 88*(3), 825–851. https://doi.org/10.2308/accr-50378

Black, E. L., & Carnes, T. A. (2006). Analysts' forecasts in Asian-Pacific markets: The relationship among macroeconomic factors, accounting systems, bias and accuracy. *Journal of International Financial Management and Accounting, 17*(3), 208–227. https://doi.org/10.1111/j.1467-646X.2006.00127.x

Bonini, S., Zanetti, L., Bianchini, R., & Salvi, A. (2010). Target price accuracy in equity research. *Journal of Business Finance & Accounting, 37*(9–10), 1177–1217. https://doi.org/10.1111/j.1468-5957.2010.02209.x

Bradshaw, M. T. (2004). How do analysts use their earnings forecasts in generating stock recommendations? *The Accounting Review, 79*(1), 25–50. https://doi.org/10.2308/accr.2004.79.1.25

Bradshaw, M. T., Brown, L. D., & Huang, K. (2013). Do sell-side analysts exhibit differential target price forecasting ability? *Review of Accounting Studies, 18*(4), 930–955. https://doi.org/10.1007/s11142-012-9216-5

Bradshaw, M. T., Huang, A. G., & Tan, H. (2012). *Analyst target price optimism around the world* [Working paper]. SSRN. https://doi.org/10.2139/ssrn.2137291

Bradshaw, M. T., Huang, A. G., & Tan, H. (2019). The effects of analyst-country institutions on biased research: Evidence from target prices. *Journal of Accounting Research, 57*(1), 85–120. https://doi.org/10.1111/1475-679X.12245

Brav, A., & Lehavy, R. (2003). An empirical analysis of analysts' target prices: Short-term informativeness and long-term dynamics. *The Journal of Finance, 58*(5), 1933–1967. https://doi.org/10.1111/1540-6261.00593

Chae, J., & Kim, R. (2026). Dispersion in analysts' target prices and stock returns in the Korean stock market. *Korean Journal of Financial Studies, 55*(5), 399–440. https://doi.org/10.26845/KJFS.2026.10.55.5.399

Chan, K., & Hameed, A. (2006). Stock price synchronicity and analyst coverage in emerging markets. *Journal of Financial Economics, 80*(1), 115–147. https://doi.org/10.1016/j.jfineco.2005.03.010

Chirabandhu, P. (2019). *Investors attention properties regarding target prices, PE ratios and their investment implications* [Independent study, Chulalongkorn University]. https://doi.org/10.58837/CHULA.IS.2019.58

Choi, Y.-S., Mira, S., & Taylor, N. (2021). Local versus foreign analysts' forecast accuracy: Does herding matter? *Accounting & Finance, 62*(S1), 1143–1188. https://doi.org/10.1111/acfi.12820

Clement, M. B., & Tse, S. Y. (2005). Financial analyst characteristics and herding behavior in forecasting. *The Journal of Finance, 60*(1), 307–341. https://doi.org/10.1111/j.1540-6261.2005.00731.x

Coën, A., & Desfleurs, A. (2004). The evolution of financial analysts' forecasts on Asian emerging markets. *Journal of Multinational Financial Management, 14*(4–5), 335–352. https://doi.org/10.1016/j.mulfin.2004.02.001

Da, Z., & Schaumburg, E. (2011). Relative valuation and analyst target price forecasts. *Journal of Financial Markets, 14*(1), 161–192. https://doi.org/10.1016/j.finmar.2010.09.001

Dechow, P. M., & You, H. (2020). Understanding the determinants of analyst target price implied returns. *The Accounting Review, 95*(6), 125–149. https://doi.org/10.2308/tar-2015-0265

Diether, K. B., Malloy, C. J., & Scherbina, A. (2002). Differences of opinion and the cross section of stock returns. *The Journal of Finance, 57*(5), 2113–2141. https://doi.org/10.1111/0022-1082.00490

Graham, J. R. (1999). Herding among investment newsletters: Theory and evidence. *The Journal of Finance, 54*(1), 237–268. https://doi.org/10.1111/0022-1082.00103

Hong, H., Kubik, J. D., & Solomon, A. (2000). Security analysts' career concerns and herding of earnings forecasts. *The RAND Journal of Economics, 31*(1), 121. https://doi.org/10.2307/2601032

Huang, R., Krishnan, M., & Shon, J. (2017). Who herds? Who doesn't? Estimates of analysts' herding propensity in forecasting earnings. *Contemporary Accounting Research, 34*(1), 374–399. https://doi.org/10.1111/1911-3846.12236

Jegadeesh, N., & Kim, W. (2010). Do analysts herd? An analysis of recommendations and market reactions. *The Review of Financial Studies, 23*(2), 901–937. https://doi.org/10.1093/rfs/hhp093

Jegadeesh, N., Kim, J., Krische, S. D., & Lee, C. M. C. (2004). Analyzing the analysts: When do recommendations add value? *The Journal of Finance, 59*(3), 1083–1124. https://doi.org/10.1111/j.1540-6261.2004.00657.x

Johnson, T. C. (2004). Forecast dispersion and the cross section of expected returns. *The Journal of Finance, 59*(5), 1957–1978. https://doi.org/10.1111/j.1540-6261.2004.00688.x

Kromadit, T. (2021). *Market reactions towards changes in analysts' ratings and target prices, evidence from Thailand* [Independent study, Chulalongkorn University]. https://doi.org/10.58837/CHULA.IS.2021.64

Lai, S., & Teo, M. (2008). Home-biased analysts in emerging markets. *Journal of Financial and Quantitative Analysis, 43*(3), 685–716. https://doi.org/10.1017/S0022109000004257

Loh, R. K., & Mian, G. M. (2003). The quality of analysts' earnings forecasts during the Asian crisis: Evidence from Singapore. *Journal of Business Finance & Accounting, 30*(5–6), 749–770. https://doi.org/10.1111/1468-5957.05443

Loh, R. K., & Mian, G. M. (2006). Do accurate earnings forecasts facilitate superior investment recommendations? *Journal of Financial Economics, 80*(2), 455–483. https://doi.org/10.1016/j.jfineco.2005.03.009

Moshirian, F., Ng, D., & Wu, E. (2009). The value of stock analysts' recommendations: Evidence from emerging markets. *International Review of Financial Analysis, 18*(1–2), 74–83. https://doi.org/10.1016/j.irfa.2008.11.001

Petkajee, T. (2020). *Analysts' consensus and predictability of forward P/E ratios* [Independent study, Chulalongkorn University]. https://doi.org/10.58837/CHULA.IS.2020.59

Sayed, S. A. (2017). How much does valuation model choice matter? Target price accuracy of PE and DCF model in Asian emerging markets. *Journal of Accounting in Emerging Economies, 7*(1), 90–107. https://doi.org/10.1108/JAEE-10-2014-0055

Schmidt, C. (2020). *Inside the black box of financial analysts: What drives systematic forecast optimism?* [Independent study, Chulalongkorn University]. https://doi.org/10.58837/CHULA.IS.2020.77

Sharda, S. (2021). The short-term impact of analyst recommendations: Evidence from the Indian stock market. *Vilakshan – XIMB Journal of Management, 19*(1), 2–19. https://doi.org/10.1108/XJM-12-2020-0239

Welch, I. (2000). Herding among security analysts. *Journal of Financial Economics, 58*(3), 369–396. https://doi.org/10.1016/S0304-405X(00)00076-3

Womack, K. L. (1996). Do brokerage analysts' recommendations have investment value? *The Journal of Finance, 51*(1), 137–167. https://doi.org/10.1111/j.1540-6261.1996.tb05205.x

---

*หมายเหตุด้านวิธีการ:* ปีของสารนิพนธ์จุฬาฯ อนุมานจากรหัส DOI (เช่น `CHULA.IS.2020.x`) เพราะฐานข้อมูลไม่ได้ระบุปีไว้ รายชื่อผู้แต่งครบของ Barber et al. (2001), Bonini et al. (2010) และ Jegadeesh et al. (2004) รวบรวมจากหลายระเบียนของ Scite (ฉบับวารสารและฉบับ working paper) และจาก citation snippet เนื่องจาก Scite แสดงผู้แต่งเพียง 3 คนต่อระเบียน เลขหน้าของ Hong et al. (2000) ใน Scite ระบุเพียงหน้าแรก ข้อค้นพบของ Welch (2000) และ Moshirian et al. (2009) มาจากการสรุปของงานที่อ้างถึง (Jegadeesh & Kim, 2010; Bradshaw et al., 2019; Sharda, 2021) เพราะเข้าถึงบทคัดย่อต้นฉบับไม่ได้
