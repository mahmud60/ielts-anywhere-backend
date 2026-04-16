"""
Adds a reading test to the database and links it to the
existing IeltsTest created by seed.py.

Run after seed.py:
    python -m app.db.seed_reading
"""
import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.ielts_test import IeltsTest
from app.models.reading import (
    ReadingTest, ReadingPassage,
    ReadingQuestionGroup, ReadingQuestion,
    ReadingQuestionType,
)


async def seed():
    async with AsyncSessionLocal() as db:

        # ── Reading test ──────────────────────────────────────────────────
        rt = ReadingTest(
            title="Academic Reading Test 1",
            test_type="academic",
            is_active=True,
            is_demo=True,
        )
        db.add(rt)
        await db.flush()

        # ══════════════════════════════════════════════════════════════════
        # PASSAGE 1 — Urban Heat Islands
        # Question types: matching_headings + tfng
        # ══════════════════════════════════════════════════════════════════
        p1 = ReadingPassage(
            test_id=rt.id,
            passage_number=1,
            title="Urban Heat Islands",
            body="",
            paragraphs=[
                "A  The phenomenon of urban heat islands has become an "
                "increasingly significant concern for city planners and "
                "environmental scientists alike. As cities expand and natural "
                "landscapes are replaced by concrete and asphalt, the temperature "
                "difference between urban and rural areas can reach as much as "
                "10 degrees Celsius. This thermal disparity is primarily caused "
                "by the absorption and re-emission of heat by built surfaces, "
                "reduced vegetation cover, and waste heat from human activities "
                "such as transportation and air conditioning.",

                "B  Research conducted across major metropolitan areas has "
                "demonstrated that strategic urban greening can substantially "
                "mitigate heat island effects. A study published in Nature Cities "
                "found that increasing tree canopy coverage by just 10% in dense "
                "urban areas reduced peak summer temperatures by an average of "
                "2.3 degrees Celsius. Furthermore, the psychological and social "
                "benefits of green spaces contribute to improved mental health "
                "outcomes among city residents.",

                "C  Critics of urban greening initiatives argue that the costs "
                "of implementation are prohibitive, particularly in densely built "
                "city centres where space is scarce and land values are extremely "
                "high. However, a 2022 economic analysis from the University of "
                "Melbourne found that every dollar invested in urban tree planting "
                "generated approximately four dollars in long-term social, "
                "environmental, and economic benefits.",

                "D  Several cities have adopted innovative approaches to combat "
                "heat islands. Singapore has embedded green corridors and rooftop "
                "gardens into its urban planning code, while Melbourne has pledged "
                "to double its tree canopy by 2040. These initiatives reflect a "
                "growing consensus among urban planners that green infrastructure "
                "is not a luxury but a public health necessity.",

                "E  The relationship between urban heat and public health is "
                "particularly acute among elderly populations and those with "
                "pre-existing cardiovascular conditions. During the 2003 European "
                "heatwave, excess mortality was disproportionately concentrated "
                "in densely built urban areas with minimal green space, "
                "underscoring the life-or-death stakes of urban thermal management.",
            ],
        )
        db.add(p1)
        await db.flush()

        # Group 1 — Matching headings
        g1 = ReadingQuestionGroup(
            passage_id=p1.id,
            order_index=1,
            question_type=ReadingQuestionType.matching_headings,
            instruction=(
                "The passage has five paragraphs labelled A–E. "
                "Choose the correct heading for each paragraph "
                "from the list of headings below."
            ),
            heading_options=[
                "i    The financial case for green urban spaces",
                "ii   Health consequences of urban heat",
                "iii  Cities taking action on heat management",
                "iv   Defining the urban heat island problem",
                "v    Evidence that vegetation reduces urban temperatures",
                "vi   Government policy on carbon emissions",
                "vii  Opposition to greening programmes",
            ],
        )
        db.add(g1)
        await db.flush()

        for order, text, key, tip in [
            (1, "Paragraph A", "iv",
             "Paragraph A introduces the definition and causes of urban heat islands. Heading iv matches directly."),
            (2, "Paragraph B", "v",
             "Paragraph B presents evidence (the Nature Cities study) that vegetation reduces temperatures. Heading v matches."),
            (3, "Paragraph C", "vii",
             "Paragraph C discusses critics who oppose greening as too costly. Heading vii matches."),
            (4, "Paragraph D", "iii",
             "Paragraph D describes cities like Singapore and Melbourne taking concrete action. Heading iii matches."),
            (5, "Paragraph E", "ii",
             "Paragraph E discusses excess mortality during the 2003 heatwave — health consequences of urban heat."),
        ]:
            db.add(ReadingQuestion(
                group_id=g1.id, order_index=order,
                question_text=text, answer_key=key, wrong_answer_tip=tip,
            ))

        # Group 2 — True / False / Not Given
        g2 = ReadingQuestionGroup(
            passage_id=p1.id,
            order_index=2,
            question_type=ReadingQuestionType.tfng,
            instruction=(
                "Do the following statements agree with the information "
                "in the passage? Write TRUE, FALSE, or NOT GIVEN."
            ),
        )
        db.add(g2)
        await db.flush()

        for order, text, key, tip in [
            (1,
             "The temperature difference between urban and rural areas can exceed 10°C.",
             1,  # FALSE — passage says "as much as 10", not exceeding
             "The passage says 'as much as 10 degrees' — up to 10, not exceeding 10. The statement is False."),
            (2,
             "Increasing tree canopy by 10% reduced temperatures by 2.3°C on average.",
             0,  # TRUE
             None),
            (3,
             "The University of Melbourne study was funded by the Singapore government.",
             2,  # NOT GIVEN — funding source never mentioned
             "The passage mentions the study but says nothing about its funding. This is Not Given."),
            (4,
             "Melbourne has committed to doubling its tree canopy by 2040.",
             0,  # TRUE
             None),
            (5,
             "The 2003 European heatwave caused more deaths in rural areas than urban ones.",
             1,  # FALSE
             "The passage says mortality was 'disproportionately concentrated in densely built urban areas' — the opposite."),
        ]:
            db.add(ReadingQuestion(
                group_id=g2.id, order_index=order,
                question_text=text, answer_key=key, wrong_answer_tip=tip,
            ))

        # ══════════════════════════════════════════════════════════════════
        # PASSAGE 2 — The Science of Sleep
        # Question types: mcq + matching_info
        # ══════════════════════════════════════════════════════════════════
        p2 = ReadingPassage(
            test_id=rt.id,
            passage_number=2,
            title="The Science of Sleep",
            body=(
                "A  Sleep is far from the passive, uniform state it appears "
                "from the outside. The brain cycles through distinct stages "
                "roughly every 90 minutes throughout the night, alternating "
                "between non-rapid eye movement (NREM) sleep and rapid eye "
                "movement (REM) sleep. NREM sleep itself has three stages, "
                "progressing from light sleep to the deep, slow-wave sleep "
                "that is critical for physical restoration and immune function.\n\n"

                "B  REM sleep, characterised by rapid eye movements and "
                "temporary muscle paralysis, is the stage most closely "
                "associated with dreaming and emotional memory consolidation. "
                "Neuroscientists at UC Berkeley have demonstrated that REM sleep "
                "acts as an 'emotional first aid', stripping the emotional charge "
                "from difficult memories while preserving their factual content.\n\n"

                "C  Chronic sleep deprivation has wide-ranging physiological "
                "consequences. Studies consistently link fewer than six hours "
                "of sleep per night with elevated risks of cardiovascular disease, "
                "type 2 diabetes, and obesity. The mechanism involves dysregulation "
                "of the hormones leptin and ghrelin, causing sleep-deprived "
                "individuals to consume an average of 385 additional calories per day.\n\n"

                "D  Adolescents are particularly vulnerable to sleep disruption "
                "because the circadian clock shifts forward during puberty, making "
                "early school start times biologically misaligned with teenage sleep "
                "needs. The American Academy of Paediatrics has recommended that "
                "middle and high schools begin no earlier than 8:30 a.m.\n\n"

                "E  The global sleep economy was valued at over 80 billion dollars "
                "in 2023 and is projected to exceed 130 billion dollars by 2030. "
                "Critics note that many commercial sleep products lack rigorous "
                "clinical evidence, and that basic sleep hygiene practices such as "
                "consistent sleep schedules are more reliably effective."
            ),
            paragraphs=None,
        )
        db.add(p2)
        await db.flush()

        # Group 3 — MCQ
        g3 = ReadingQuestionGroup(
            passage_id=p2.id,
            order_index=1,
            question_type=ReadingQuestionType.mcq,
            instruction=(
                "Choose the correct letter A, B, C, or D."
            ),
        )
        db.add(g3)
        await db.flush()

        for order, text, options, key, tip in [
            (1,
             "According to the passage, how often does the brain complete a full sleep cycle?",
             ["Every 60 minutes", "Every 90 minutes", "Every two hours", "Every three hours"],
             1, "The passage states 'roughly every 90 minutes'. Read numbers carefully."),
            (2,
             "What does UC Berkeley research suggest about REM sleep?",
             ["It improves physical recovery more than NREM sleep",
              "It removes emotional intensity from difficult memories",
              "It is responsible for most dreaming content",
              "It is disrupted by cardiovascular disease"],
             1, "'Stripping the emotional charge from difficult memories' — option B paraphrases this."),
            (3,
             "Which best describes the effect of sleep deprivation on eating behaviour?",
             ["It reduces appetite by suppressing ghrelin",
              "It causes a preference for high-fat foods",
              "It leads to consuming significantly more calories daily",
              "It directly disrupts insulin production"],
             2, "The passage says '385 additional calories per day' — this matches option C."),
            (4,
             "What is the American Academy of Paediatrics' position on school start times?",
             ["Schools should allow flexible start times for teenagers",
              "Teenagers need more sleep than younger children",
              "Middle and high schools should start no earlier than 8:30 a.m.",
              "Circadian rhythms stabilise after puberty"],
             2, None),
        ]:
            db.add(ReadingQuestion(
                group_id=g3.id, order_index=order, question_text=text,
                options=options, answer_key=key, wrong_answer_tip=tip,
            ))

        # Group 4 — Matching information (statement → paragraph letter)
        g4 = ReadingQuestionGroup(
            passage_id=p2.id,
            order_index=2,
            question_type=ReadingQuestionType.matching_info,
            instruction=(
                "The passage has five paragraphs labelled A–E. "
                "Which paragraph contains the following information? "
                "You may use any letter more than once."
            ),
            paragraph_labels=["A", "B", "C", "D", "E"],
        )
        db.add(g4)
        await db.flush()

        for order, text, key, tip in [
            (1,
             "A reference to a recommendation made by a professional organisation.",
             "D",
             "Paragraph D contains the American Academy of Paediatrics' recommendation — a professional organisation."),
            (2,
             "A description of sleep's role in processing emotions.",
             "B",
             "Paragraph B discusses REM sleep as 'emotional first aid' and emotional memory consolidation."),
            (3,
             "A claim that certain sleep-aid products may not be scientifically validated.",
             "E",
             "Paragraph E states 'many commercial sleep products lack rigorous clinical evidence'."),
            (4,
             "An explanation of how poor sleep leads to weight-related issues.",
             "C",
             "Paragraph C explains leptin/ghrelin dysregulation causing sleep-deprived people to eat more."),
        ]:
            db.add(ReadingQuestion(
                group_id=g4.id, order_index=order,
                question_text=text, answer_key=key, wrong_answer_tip=tip,
            ))

        # ══════════════════════════════════════════════════════════════════
        # PASSAGE 3 — The Columbian Exchange
        # Question types: fill + short_answer
        # ══════════════════════════════════════════════════════════════════
        p3 = ReadingPassage(
            test_id=rt.id,
            passage_number=3,
            title="The Columbian Exchange",
            body=(
                "The Columbian Exchange — the transfer of plants, animals, culture, "
                "human populations, technology, and ideas between the Americas and "
                "the Old World following Columbus's 1492 voyage — fundamentally "
                "reshaped global agriculture, diet, and demography. Crops including "
                "the potato, maize, tomato, and cacao transformed European and Asian "
                "cuisines within a remarkably short historical timeframe.\n\n"

                "The potato had an outsized demographic impact in Europe. Historian "
                "William McNeill estimated that its adoption in Ireland, Germany, and "
                "Eastern Europe enabled population growth of roughly 25 percent between "
                "the mid-eighteenth and mid-nineteenth centuries. Its caloric density "
                "and ease of cultivation made it an ideal food security crop for peasant "
                "populations who had previously faced recurring famine.\n\n"

                "The exchange was profoundly asymmetric in its consequences. While Europe "
                "gained nutritious crops, the Americas received Old World diseases — most "
                "devastatingly smallpox — against which indigenous populations had no "
                "immunity. Epidemiologists estimate that between 50 and 90 percent of the "
                "indigenous population of the Americas died within a century of first "
                "contact, a demographic catastrophe without parallel in recorded history.\n\n"

                "Animal transfers also had lasting consequences. The introduction of horses "
                "transformed the cultures of Plains tribes, enabling new forms of buffalo "
                "hunting and warfare. Old World animals including cattle, pigs, and sheep "
                "contributed to environmental degradation through overgrazing, altering "
                "ecosystems that had evolved without large domesticated herbivores.\n\n"

                "Scholars debate whether 'exchange' adequately captures the power dynamics "
                "at play. Critics argue that it implies a voluntary and equal transaction, "
                "whereas the biological consequences for indigenous peoples were neither "
                "chosen nor reciprocal. Some historians prefer 'Columbian encounter' to "
                "acknowledge this imbalance, though 'Columbian Exchange' remains dominant "
                "in academic literature."
            ),
            paragraphs=None,
        )
        db.add(p3)
        await db.flush()

        # Group 5 — Fill in the blank
        g5 = ReadingQuestionGroup(
            passage_id=p3.id,
            order_index=1,
            question_type=ReadingQuestionType.fill,
            instruction=(
                "Complete the sentences below. "
                "Choose NO MORE THAN TWO WORDS from the passage for each answer."
            ),
            word_limit="NO MORE THAN TWO WORDS",
        )
        db.add(g5)
        await db.flush()

        for order, text, key, tip in [
            (1,
             "William McNeill estimated that the potato enabled population growth of roughly ___________ in parts of Europe.",
             "25 percent",
             "The passage states 'population growth of roughly 25 percent'. Copy the figure exactly."),
            (2,
             "The potato suited ___________ populations because of its caloric density and ease of cultivation.",
             "peasant",
             "The passage says 'peasant populations' — use the exact word from the text."),
            (3,
             "The most devastating Old World disease introduced to the Americas was ___________.",
             "smallpox",
             "The passage explicitly names smallpox. Scan for 'devastatingly' to locate the answer."),
            (4,
             "Historians who object to the term 'exchange' sometimes prefer '___________ encounter' instead.",
             "columbian",
             "The passage offers 'Columbian encounter' as an alternative. Only 'Columbian' is needed here."),
        ]:
            db.add(ReadingQuestion(
                group_id=g5.id, order_index=order,
                question_text=text,
                answer_key=key.lower(),
                wrong_answer_tip=tip,
            ))

        # Group 6 — Short answer
        g6 = ReadingQuestionGroup(
            passage_id=p3.id,
            order_index=2,
            question_type=ReadingQuestionType.short_answer,
            instruction=(
                "Answer the questions below. "
                "Choose NO MORE THAN THREE WORDS from the passage for each answer."
            ),
            word_limit="NO MORE THAN THREE WORDS",
        )
        db.add(g6)
        await db.flush()

        for order, text, keys, tip in [
            (1,
             "Name TWO crops from the Americas mentioned in the passage.",
             ["potato and maize", "maize and potato", "potato and tomato",
              "tomato and potato", "potato", "maize", "tomato", "cacao"],
             "The passage lists potato, maize, tomato, and cacao. Any two are correct."),
            (2,
             "What did horses enable Plains tribes to do, according to the passage?",
             ["buffalo hunting", "hunt buffalo", "buffalo hunting and warfare",
              "new forms of buffalo hunting", "buffalo hunting and warfare"],
             "The passage says horses enabled 'new forms of buffalo hunting and warfare'."),
            (3,
             "What environmental problem did Old World animals cause in the Americas?",
             ["overgrazing", "environmental degradation",
              "ecosystem alteration", "environmental degradation through overgrazing"],
             "The passage mentions 'environmental degradation through overgrazing'."),
        ]:
            db.add(ReadingQuestion(
                group_id=g6.id, order_index=order,
                question_text=text,
                answer_key=[k.lower() for k in keys],
                wrong_answer_tip=tip,
            ))

        # ── Link reading test to the existing IeltsTest ───────────────────
        ielts = (await db.execute(
            select(IeltsTest).where(IeltsTest.is_active == True).limit(1)
        )).scalar_one_or_none()

        if not ielts:
            print("No IeltsTest found — run seed.py first")
            await db.rollback()
            return

        ielts.reading_test_id = rt.id
        await db.commit()

        print(f"\nSeeded reading test: {rt.id}")
        print(f"  Passage 1 — Urban Heat Islands")
        print(f"    Matching Headings: 5 questions")
        print(f"    True/False/Not Given: 5 questions")
        print(f"  Passage 2 — The Science of Sleep")
        print(f"    MCQ: 4 questions")
        print(f"    Matching Information: 4 questions")
        print(f"  Passage 3 — The Columbian Exchange")
        print(f"    Fill in the Blank: 4 questions")
        print(f"    Short Answer: 3 questions")
        print(f"  Total: 25 questions across 3 passages")
        print(f"\nLinked to IeltsTest: {ielts.id}")


if __name__ == "__main__":
    asyncio.run(seed())