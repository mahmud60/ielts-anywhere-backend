"""
Creates one complete IeltsTest with linked listening and reading tests.
Run once after migrations.

    python -m app.db.seed
"""
import asyncio
from app.db.session import AsyncSessionLocal
from app.models.listening import ListeningTest, ListeningSection, ListeningSubsection, ListeningQuestion
from app.models.reading import (
    ReadingTest, ReadingPassage, ReadingQuestionGroup, ReadingQuestion, ReadingQuestionType,
)
from app.models.ielts_test import IeltsTest


def opts(*labels):
    return [{"order": i, "option": lbl} for i, lbl in enumerate(labels)]


async def seed():
    async with AsyncSessionLocal() as db:

        # ── Listening test ────────────────────────────────────────────────────
        lt = ListeningTest(title="Academic Listening Test 1", is_active=True)
        db.add(lt)
        await db.flush()

        s1 = ListeningSection(test_id=lt.id, part=1, title="Hotel Booking")
        db.add(s1)
        await db.flush()
        sub1 = ListeningSubsection(section_id=s1.id, order=1, subsection_type="regular",
            text="Questions 1–4. Choose the correct letter, A, B, C or D.")
        db.add(sub1)
        await db.flush()
        for q in [
            ListeningQuestion(subsection_id=sub1.id, order=1,
                question_type="multiple_choices",
                text="What is the main purpose of the caller's enquiry?",
                options=opts("To cancel a booking", "To make a new reservation", "To complain", "To ask about prices"),
                answer_key="1",
                wrong_answer_tip="Listen to the caller's opening sentence — purpose is stated directly."),
            ListeningQuestion(subsection_id=sub1.id, order=2,
                question_type="fill_in_the_blank",
                text="The guest's last name is ___________.",
                answer_key="thompson",
                wrong_answer_tip="Proper nouns are usually spelled out. Listen for T-H-O-M-P-S-O-N."),
            ListeningQuestion(subsection_id=sub1.id, order=3,
                question_type="fill_in_the_blank",
                text="The check-in date is ___________ 14th.",
                answer_key="march",
                wrong_answer_tip="Dates are spoken as ordinals. 'The fourteenth of March' means March 14th."),
            ListeningQuestion(subsection_id=sub1.id, order=4,
                question_type="multiple_choices",
                text="How many nights does the guest plan to stay?",
                options=opts("Two nights", "Three nights", "Four nights", "Five nights"),
                answer_key="1",
                wrong_answer_tip=None),
        ]:
            db.add(q)

        s2 = ListeningSection(test_id=lt.id, part=2, title="Community Centre")
        db.add(s2)
        await db.flush()
        sub2 = ListeningSubsection(section_id=s2.id, order=1, subsection_type="regular",
            text="Questions 5–7. Do the following statements agree with the information?")
        db.add(sub2)
        await db.flush()
        for q in [
            ListeningQuestion(subsection_id=sub2.id, order=1,
                question_type="multiple_choices",
                text="The community centre has been recently renovated.",
                options=opts("True", "False", "Not Given"),
                answer_key="0",
                wrong_answer_tip="Listen for 'newly refurbished' or 'recently updated'."),
            ListeningQuestion(subsection_id=sub2.id, order=2,
                question_type="multiple_choices",
                text="Fitness classes are available every day of the week.",
                options=opts("True", "False", "Not Given"),
                answer_key="1",
                wrong_answer_tip="Listen for days mentioned — 'Monday to Saturday' excludes Sunday."),
            ListeningQuestion(subsection_id=sub2.id, order=3,
                question_type="multiple_choices",
                text="The centre offers discounts for senior citizens.",
                options=opts("True", "False", "Not Given"),
                answer_key="2",
                wrong_answer_tip="Not Given — the recording never mentions senior discounts at all."),
        ]:
            db.add(q)

        s3 = ListeningSection(test_id=lt.id, part=3, title="Research Discussion")
        db.add(s3)
        await db.flush()
        sub3 = ListeningSubsection(section_id=s3.id, order=1, subsection_type="form",
            text="Questions 8–9. Complete the form below.")
        db.add(sub3)
        await db.flush()
        for q in [
            ListeningQuestion(subsection_id=sub3.id, order=1,
                question_type="dropdown",
                text="Research method suggested by Student A",
                options=opts("Conducting surveys", "Reviewing existing literature", "Running lab experiments"),
                answer_key="0",
                wrong_answer_tip="Speakers use synonyms — 'questionnaire' means survey."),
            ListeningQuestion(subsection_id=sub3.id, order=2,
                question_type="multiple_choices",
                text="What does the supervisor recommend as the next step?",
                options=opts("Submit the proposal immediately", "Narrow down the research question",
                             "Collect data first", "Present to the department"),
                answer_key="1",
                wrong_answer_tip=None),
        ]:
            db.add(q)

        s4 = ListeningSection(test_id=lt.id, part=4, title="Urban Heat Islands")
        db.add(s4)
        await db.flush()
        sub4 = ListeningSubsection(section_id=s4.id, order=1, subsection_type="regular",
            text="Questions 10–12. Complete the notes below.")
        db.add(sub4)
        await db.flush()
        for q in [
            ListeningQuestion(subsection_id=sub4.id, order=1,
                question_type="fill_in_the_blank",
                text="Urban areas can be up to ___________ degrees warmer than rural regions.",
                answer_key="10",
                wrong_answer_tip="Numbers in lectures are emphasised. Listen for 'up to' or 'as much as'."),
            ListeningQuestion(subsection_id=sub4.id, order=2,
                question_type="multiple_choices",
                text="Which factor does the lecturer identify as the PRIMARY cause?",
                options=opts("Vehicle emissions", "Reduced green spaces",
                             "Heat absorption by built surfaces", "Waste heat from air conditioning"),
                answer_key="2",
                wrong_answer_tip="Listen for 'primarily', 'mainly', or 'the most significant factor'."),
            ListeningQuestion(subsection_id=sub4.id, order=3,
                question_type="fill_in_the_blank",
                text="Increasing tree canopy by 10% reduces temperatures by ___________ degrees Celsius.",
                answer_key="2.3",
                wrong_answer_tip="Decimals are easy to mishear. '2.3' is 'two point three'."),
        ]:
            db.add(q)

        # ── Reading test ──────────────────────────────────────────────────────
        rt = ReadingTest(title="Academic Reading Test 1", test_type="academic", is_active=True)
        db.add(rt)
        await db.flush()

        # ── Passage 1: Urban Heat Islands ─────────────────────────────────────
        p1 = ReadingPassage(
            test_id=rt.id, passage_number=1,
            title="Urban Heat Islands",
            body=(
                "Urban heat islands (UHIs) are metropolitan areas significantly warmer than their "
                "surrounding rural regions. This thermal disparity, which can reach up to 10 degrees "
                "Celsius, arises primarily from the replacement of natural land cover with dense "
                "concentrations of pavement, buildings, and other surfaces that absorb and retain heat. "
                "Human activities such as transportation, industry, and air conditioning also contribute "
                "substantial waste heat to the urban environment.\n\n"
                "The consequences of UHIs extend beyond mere discomfort. Elevated temperatures increase "
                "energy consumption as residents run cooling systems for longer periods. This, in turn, "
                "drives up greenhouse gas emissions, creating a feedback loop that intensifies climate "
                "change at both local and global scales. Public health is equally affected: heat-related "
                "illnesses and mortality spike during urban heat events, particularly among elderly "
                "populations and those with pre-existing cardiovascular conditions.\n\n"
                "Mitigation strategies have been studied extensively. Increasing urban tree canopy is "
                "among the most effective interventions — research shows that a 10% rise in canopy cover "
                "can lower surface temperatures by approximately 2.3 degrees Celsius. Green roofs and "
                "cool pavements, which reflect rather than absorb solar radiation, are increasingly "
                "deployed in forward-thinking cities. Urban planners also advocate for the preservation "
                "of water bodies and wetlands, which regulate temperature through evaporative cooling. "
                "While no single solution is sufficient, evidence suggests that combining multiple "
                "strategies produces synergistic benefits far exceeding individual measures."
            ),
        )
        db.add(p1)
        await db.flush()

        # Group 1 — MCQ (4 questions)
        g1_1 = ReadingQuestionGroup(
            passage_id=p1.id, order_index=1,
            question_type=ReadingQuestionType.mcq,
            instruction="Choose the correct letter, A, B, C or D.",
        )
        db.add(g1_1)
        await db.flush()
        for q in [
            ReadingQuestion(group_id=g1_1.id, order_index=1,
                question_text="What is the PRIMARY cause of urban heat islands according to the passage?",
                options=["Human waste heat from industry", "Replacement of natural land with heat-retaining surfaces",
                         "Increased greenhouse gas emissions", "Higher population density"],
                answer_key=1,
                wrong_answer_tip="The passage says UHIs arise 'primarily from the replacement of natural land cover' — not from waste heat."),
            ReadingQuestion(group_id=g1_1.id, order_index=2,
                question_text="According to the passage, how does the UHI effect influence energy use?",
                options=["It reduces the need for heating systems", "It increases cooling system usage",
                         "It has no measurable effect on consumption", "It lowers industrial energy demand"],
                answer_key=1,
                wrong_answer_tip="The second paragraph explicitly states elevated temperatures increase energy consumption through cooling systems."),
            ReadingQuestion(group_id=g1_1.id, order_index=3,
                question_text="Which group is described as particularly vulnerable to heat-related health risks?",
                options=["Children under 12", "Athletes and outdoor workers",
                         "Elderly people and those with heart conditions", "Low-income households"],
                answer_key=2,
                wrong_answer_tip="The passage specifically names 'elderly populations and those with pre-existing cardiovascular conditions'."),
            ReadingQuestion(group_id=g1_1.id, order_index=4,
                question_text="What does the passage suggest about combining multiple mitigation strategies?",
                options=["Results are no better than a single strategy", "It produces effects greater than individual measures",
                         "It is too costly for most cities", "It has not yet been studied"],
                answer_key=1,
                wrong_answer_tip="The final sentence mentions 'synergistic benefits far exceeding individual measures'."),
        ]:
            db.add(q)

        # Group 2 — TFNG (4 questions)
        g1_2 = ReadingQuestionGroup(
            passage_id=p1.id, order_index=2,
            question_type=ReadingQuestionType.tfng,
            instruction=(
                "Do the following statements agree with the information in the passage? "
                "Write TRUE, FALSE or NOT GIVEN. "
                "0 = True, 1 = False, 2 = Not Given"
            ),
        )
        db.add(g1_2)
        await db.flush()
        for q in [
            ReadingQuestion(group_id=g1_2.id, order_index=1,
                question_text="The temperature difference between urban and rural areas can be as large as 10°C.",
                options=None, answer_key=0,
                wrong_answer_tip="The passage states the disparity 'can reach up to 10 degrees Celsius' — TRUE."),
            ReadingQuestion(group_id=g1_2.id, order_index=2,
                question_text="Air conditioning contributes to urban heat but is not mentioned as a significant factor.",
                options=None, answer_key=1,
                wrong_answer_tip="The passage explicitly lists air conditioning as contributing 'substantial waste heat' — FALSE."),
            ReadingQuestion(group_id=g1_2.id, order_index=3,
                question_text="Green roofs have been shown to be more effective than increased tree canopy.",
                options=None, answer_key=2,
                wrong_answer_tip="The passage mentions both strategies but makes no comparison between them — NOT GIVEN."),
            ReadingQuestion(group_id=g1_2.id, order_index=4,
                question_text="Preserving water bodies helps regulate urban temperatures.",
                options=None, answer_key=0,
                wrong_answer_tip="The passage states water bodies 'regulate temperature through evaporative cooling' — TRUE."),
        ]:
            db.add(q)

        # Group 3 — Fill (3 questions)
        g1_3 = ReadingQuestionGroup(
            passage_id=p1.id, order_index=3,
            question_type=ReadingQuestionType.fill,
            instruction="Complete the sentences below. Use NO MORE THAN TWO WORDS from the passage.",
            word_limit="NO MORE THAN TWO WORDS",
        )
        db.add(g1_3)
        await db.flush()
        for q in [
            ReadingQuestion(group_id=g1_3.id, order_index=1,
                question_text="Surfaces in urban areas absorb and retain ___________, raising temperatures.",
                options=None, answer_key="heat",
                wrong_answer_tip="Scan for what the surfaces do — 'absorb and retain heat'."),
            ReadingQuestion(group_id=g1_3.id, order_index=2,
                question_text="UHI-related feedback loops can intensify ___________ at both local and global scales.",
                options=None, answer_key="climate change",
                wrong_answer_tip="The second paragraph explains the greenhouse-gas feedback leads to 'climate change'."),
            ReadingQuestion(group_id=g1_3.id, order_index=3,
                question_text="Cool pavements work by ___________ solar radiation rather than absorbing it.",
                options=None, answer_key="reflecting",
                wrong_answer_tip="The passage says cool pavements 'reflect rather than absorb solar radiation'."),
        ]:
            db.add(q)

        # ── Passage 2: The Psychology of Decision Making ──────────────────────
        p2 = ReadingPassage(
            test_id=rt.id, passage_number=2,
            title="The Psychology of Decision Making",
            body=(
                "A  For decades, economists modelled human beings as rational agents who consistently "
                "maximise their own utility. The emergence of behavioural economics challenged this "
                "assumption fundamentally, demonstrating that cognitive biases and emotional states "
                "regularly cause people to make decisions that diverge from strictly rational outcomes.\n\n"
                "B  One of the most extensively documented phenomena is loss aversion — the tendency "
                "for individuals to feel the pain of a loss roughly twice as intensely as the pleasure "
                "derived from an equivalent gain. This asymmetry was first formalised by Daniel Kahneman "
                "and Amos Tversky in their landmark Prospect Theory, published in 1979, and has since "
                "been replicated across cultures and age groups.\n\n"
                "C  Anchoring is another pervasive bias. When people are asked to estimate an unknown "
                "quantity, they tend to rely disproportionately on the first piece of information "
                "they encounter — the 'anchor' — even when that anchor is arbitrary or irrelevant. "
                "In one classic experiment, participants who spun a wheel landing on a high number "
                "subsequently gave higher estimates of the percentage of African nations in the UN "
                "than those whose wheel landed on a low number.\n\n"
                "D  The availability heuristic leads people to judge the likelihood of events based "
                "on how easily examples come to mind. Plane crashes receive far more media coverage "
                "than the statistically more common causes of death, leading many people to overestimate "
                "aviation risk while underestimating dangers such as heart disease.\n\n"
                "E  Overconfidence is particularly prevalent among experts. Studies of physicians, "
                "lawyers, engineers, and financial analysts consistently reveal that professionals "
                "overestimate the accuracy of their own predictions. This has direct implications for "
                "risk assessment in fields ranging from medicine to finance.\n\n"
                "F  Nudge theory, developed by Thaler and Sunstein, applies insights from behavioural "
                "economics to policy design. By restructuring the 'choice architecture' — the environment "
                "in which decisions are made — governments and institutions can guide people towards "
                "better outcomes without restricting freedom of choice. Automatic pension enrolment, "
                "calorie labels on menus, and organ donation opt-out systems are all examples of nudges "
                "that have produced measurable improvements in public welfare."
            ),
            paragraphs=[
                "A  For decades, economists modelled human beings as rational agents who consistently maximise their own utility. The emergence of behavioural economics challenged this assumption fundamentally, demonstrating that cognitive biases and emotional states regularly cause people to make decisions that diverge from strictly rational outcomes.",
                "B  One of the most extensively documented phenomena is loss aversion — the tendency for individuals to feel the pain of a loss roughly twice as intensely as the pleasure derived from an equivalent gain. This asymmetry was first formalised by Daniel Kahneman and Amos Tversky in their landmark Prospect Theory, published in 1979, and has since been replicated across cultures and age groups.",
                "C  Anchoring is another pervasive bias. When people are asked to estimate an unknown quantity, they tend to rely disproportionately on the first piece of information they encounter — the 'anchor' — even when that anchor is arbitrary or irrelevant. In one classic experiment, participants who spun a wheel landing on a high number subsequently gave higher estimates of the percentage of African nations in the UN than those whose wheel landed on a low number.",
                "D  The availability heuristic leads people to judge the likelihood of events based on how easily examples come to mind. Plane crashes receive far more media coverage than the statistically more common causes of death, leading many people to overestimate aviation risk while underestimating dangers such as heart disease.",
                "E  Overconfidence is particularly prevalent among experts. Studies of physicians, lawyers, engineers, and financial analysts consistently reveal that professionals overestimate the accuracy of their own predictions. This has direct implications for risk assessment in fields ranging from medicine to finance.",
                "F  Nudge theory, developed by Thaler and Sunstein, applies insights from behavioural economics to policy design. By restructuring the 'choice architecture' — the environment in which decisions are made — governments and institutions can guide people towards better outcomes without restricting freedom of choice. Automatic pension enrolment, calorie labels on menus, and organ donation opt-out systems are all examples of nudges that have produced measurable improvements in public welfare.",
            ],
        )
        db.add(p2)
        await db.flush()

        # Group 1 — Matching headings (6 paragraphs → 6 headings)
        g2_1 = ReadingQuestionGroup(
            passage_id=p2.id, order_index=1,
            question_type=ReadingQuestionType.matching_headings,
            instruction="The passage has six paragraphs labelled A–F. Match each paragraph with the correct heading.",
            heading_options=[
                "i    A challenge to the rational model of economics",
                "ii   How early information distorts estimates",
                "iii  The role of media in shaping perceived risk",
                "iv   Applying behavioural insights to public policy",
                "v    Systematic overestimation of personal expertise",
                "vi   Why losses hurt more than gains feel good",
            ],
        )
        db.add(g2_1)
        await db.flush()
        for q in [
            ReadingQuestion(group_id=g2_1.id, order_index=1,
                question_text="Paragraph A",
                options=None, answer_key="i",
                wrong_answer_tip="Paragraph A introduces behavioural economics as a challenge to rational-agent theory."),
            ReadingQuestion(group_id=g2_1.id, order_index=2,
                question_text="Paragraph B",
                options=None, answer_key="vi",
                wrong_answer_tip="Paragraph B is entirely about loss aversion — losses hurting more than gains please."),
            ReadingQuestion(group_id=g2_1.id, order_index=3,
                question_text="Paragraph C",
                options=None, answer_key="ii",
                wrong_answer_tip="Paragraph C describes anchoring — how the first piece of information distorts later estimates."),
            ReadingQuestion(group_id=g2_1.id, order_index=4,
                question_text="Paragraph D",
                options=None, answer_key="iii",
                wrong_answer_tip="Paragraph D explains how media coverage of plane crashes makes aviation seem riskier than it is."),
            ReadingQuestion(group_id=g2_1.id, order_index=5,
                question_text="Paragraph E",
                options=None, answer_key="v",
                wrong_answer_tip="Paragraph E discusses overconfidence, specifically that experts overestimate their own accuracy."),
            ReadingQuestion(group_id=g2_1.id, order_index=6,
                question_text="Paragraph F",
                options=None, answer_key="iv",
                wrong_answer_tip="Paragraph F is about nudge theory — applying behavioural economics to policy."),
        ]:
            db.add(q)

        # Group 2 — Matching information (4 questions)
        g2_2 = ReadingQuestionGroup(
            passage_id=p2.id, order_index=2,
            question_type=ReadingQuestionType.matching_info,
            instruction=(
                "Which paragraph contains the following information? "
                "You may use any letter more than once."
            ),
            paragraph_labels=["A", "B", "C", "D", "E", "F"],
        )
        db.add(g2_2)
        await db.flush()
        for q in [
            ReadingQuestion(group_id=g2_2.id, order_index=1,
                question_text="A reference to a specific published theory and its authors",
                options=None, answer_key="B",
                wrong_answer_tip="Prospect Theory by Kahneman and Tversky (1979) is mentioned in paragraph B."),
            ReadingQuestion(group_id=g2_2.id, order_index=2,
                question_text="An example involving a random spinning device",
                options=None, answer_key="C",
                wrong_answer_tip="The wheel-spinning experiment is described in paragraph C (anchoring)."),
            ReadingQuestion(group_id=g2_2.id, order_index=3,
                question_text="A mention of professional fields where a bias has serious consequences",
                options=None, answer_key="E",
                wrong_answer_tip="Paragraph E lists medicine and finance as fields affected by overconfidence."),
            ReadingQuestion(group_id=g2_2.id, order_index=4,
                question_text="Concrete examples of policy interventions that improve public welfare",
                options=None, answer_key="F",
                wrong_answer_tip="Paragraph F gives examples: pension enrolment, calorie labels, organ donation."),
        ]:
            db.add(q)

        # Group 3 — Short answer (3 questions)
        g2_3 = ReadingQuestionGroup(
            passage_id=p2.id, order_index=3,
            question_type=ReadingQuestionType.short_answer,
            instruction="Answer the questions below. Use NO MORE THAN THREE WORDS from the passage.",
            word_limit="NO MORE THAN THREE WORDS",
        )
        db.add(g2_3)
        await db.flush()
        for q in [
            ReadingQuestion(group_id=g2_3.id, order_index=1,
                question_text="What term describes the first piece of information that disproportionately influences estimates?",
                options=None, answer_key=["anchor", "the anchor"],
                wrong_answer_tip="Paragraph C defines this concept explicitly — look for the word in quotation marks."),
            ReadingQuestion(group_id=g2_3.id, order_index=2,
                question_text="Who developed nudge theory?",
                options=None, answer_key=["thaler and sunstein", "sunstein and thaler"],
                wrong_answer_tip="Paragraph F names the developers directly."),
            ReadingQuestion(group_id=g2_3.id, order_index=3,
                question_text="What phrase does the passage use to describe the environment in which decisions are made?",
                options=None, answer_key=["choice architecture"],
                wrong_answer_tip="Paragraph F puts this phrase in quotation marks — a strong signal it is the answer."),
        ]:
            db.add(q)

        # ── Passage 3: Renewable Energy Transitions ───────────────────────────
        p3 = ReadingPassage(
            test_id=rt.id, passage_number=3,
            title="Renewable Energy Transitions",
            body=(
                "The global shift towards renewable energy is accelerating at a pace that would have "
                "seemed implausible two decades ago. Solar photovoltaic costs have fallen by more than "
                "90% since 2010, and wind energy is now among the cheapest sources of new electricity "
                "generation in most markets. Yet the transition remains uneven, shaped by geography, "
                "politics, and the inertia of existing infrastructure.\n\n"
                "Grid integration presents one of the most significant technical challenges. Unlike "
                "fossil fuels, solar and wind generation is intermittent — output fluctuates with "
                "weather and time of day. Managing this variability requires investment in energy "
                "storage, demand-response systems, and high-capacity transmission lines that can "
                "transfer surplus renewable energy across regions.\n\n"
                "Battery storage technology has improved dramatically, with lithium-ion costs dropping "
                "nearly 89% between 2010 and 2023. However, batteries remain insufficient for seasonal "
                "storage — periods of prolonged low sunlight or wind that can last weeks. Long-duration "
                "storage technologies, including hydrogen electrolysis, compressed air, and gravity-based "
                "systems, are under active development but have yet to achieve commercial viability at scale.\n\n"
                "Policy frameworks play a decisive role. Countries with stable, long-term renewable "
                "energy targets and predictable regulatory environments attract far greater private "
                "investment than those with inconsistent policy signals. Feed-in tariffs, renewable "
                "portfolio standards, and carbon pricing mechanisms have each proven effective in "
                "specific national contexts, though no single model has emerged as universally optimal.\n\n"
                "The social dimensions of the transition are equally important. Communities dependent "
                "on fossil fuel industries face economic disruption as those industries contract. "
                "Without targeted investment in retraining programmes, infrastructure, and alternative "
                "economic development, energy transitions risk deepening existing inequalities rather "
                "than alleviating them. A just transition — one that distributes the costs and benefits "
                "fairly across society — is increasingly recognised as a prerequisite for political "
                "sustainability of climate policy."
            ),
        )
        db.add(p3)
        await db.flush()

        # Group 1 — MCQ (3 questions)
        g3_1 = ReadingQuestionGroup(
            passage_id=p3.id, order_index=1,
            question_type=ReadingQuestionType.mcq,
            instruction="Choose the correct letter, A, B, C or D.",
        )
        db.add(g3_1)
        await db.flush()
        for q in [
            ReadingQuestion(group_id=g3_1.id, order_index=1,
                question_text="What does the passage identify as a key technical challenge in renewable energy?",
                options=["The high cost of solar panels", "The intermittent nature of solar and wind output",
                         "A lack of government support", "Insufficient research funding"],
                answer_key=1,
                wrong_answer_tip="The second paragraph says intermittency is 'one of the most significant technical challenges'."),
            ReadingQuestion(group_id=g3_1.id, order_index=2,
                question_text="Why are current battery technologies considered insufficient for renewable energy?",
                options=["They are too expensive to manufacture", "They cannot store energy for prolonged low-generation periods",
                         "They have not improved in recent years", "They are only suitable for small-scale use"],
                answer_key=1,
                wrong_answer_tip="The passage says batteries 'remain insufficient for seasonal storage — periods of prolonged low sunlight or wind'."),
            ReadingQuestion(group_id=g3_1.id, order_index=3,
                question_text="According to the passage, what characterises countries that attract more renewable investment?",
                options=["Large land area suitable for solar farms", "Stable long-term targets and predictable regulation",
                         "Advanced battery manufacturing capacity", "High existing renewable energy share"],
                answer_key=1,
                wrong_answer_tip="Paragraph 4 states 'stable, long-term renewable energy targets and predictable regulatory environments' attract investment."),
        ]:
            db.add(q)

        # Group 2 — TFNG (3 questions)
        g3_2 = ReadingQuestionGroup(
            passage_id=p3.id, order_index=2,
            question_type=ReadingQuestionType.tfng,
            instruction=(
                "Do the following statements agree with the claims of the writer? "
                "0 = True, 1 = False, 2 = Not Given"
            ),
        )
        db.add(g3_2)
        await db.flush()
        for q in [
            ReadingQuestion(group_id=g3_2.id, order_index=1,
                question_text="Solar PV costs have decreased by over 90% since 2010.",
                options=None, answer_key=0,
                wrong_answer_tip="The first paragraph states costs 'have fallen by more than 90% since 2010' — TRUE."),
            ReadingQuestion(group_id=g3_2.id, order_index=2,
                question_text="Feed-in tariffs are the most effective policy mechanism for renewable energy globally.",
                options=None, answer_key=2,
                wrong_answer_tip="The passage says 'no single model has emerged as universally optimal' — NOT GIVEN."),
            ReadingQuestion(group_id=g3_2.id, order_index=3,
                question_text="A just transition is described as essential for the long-term political viability of climate policy.",
                options=None, answer_key=0,
                wrong_answer_tip="The final sentence calls it 'a prerequisite for political sustainability of climate policy' — TRUE."),
        ]:
            db.add(q)

        # Group 3 — Fill (3 questions)
        g3_3 = ReadingQuestionGroup(
            passage_id=p3.id, order_index=3,
            question_type=ReadingQuestionType.fill,
            instruction="Complete the sentences. Use NO MORE THAN TWO WORDS AND/OR A NUMBER from the passage.",
            word_limit="NO MORE THAN TWO WORDS AND/OR A NUMBER",
        )
        db.add(g3_3)
        await db.flush()
        for q in [
            ReadingQuestion(group_id=g3_3.id, order_index=1,
                question_text="Lithium-ion battery costs dropped by nearly ___________ between 2010 and 2023.",
                options=None, answer_key="89%",
                wrong_answer_tip="Paragraph 3 gives the exact figure: 'nearly 89% between 2010 and 2023'."),
            ReadingQuestion(group_id=g3_3.id, order_index=2,
                question_text="High-capacity ___________ can move surplus renewable energy between regions.",
                options=None, answer_key="transmission lines",
                wrong_answer_tip="Paragraph 2 lists 'high-capacity transmission lines' as part of grid management."),
            ReadingQuestion(group_id=g3_3.id, order_index=3,
                question_text="Communities reliant on fossil fuels may need ___________ programmes as those industries shrink.",
                options=None, answer_key="retraining",
                wrong_answer_tip="The final paragraph mentions 'targeted investment in retraining programmes' for affected communities."),
        ]:
            db.add(q)

        # ── IeltsTest — link both modules ─────────────────────────────────────
        ielts = IeltsTest(
            title="Academic Full Test 1",
            test_type="academic",
            is_active=True,
            listening_test_id=lt.id,
            reading_test_id=rt.id,
        )
        db.add(ielts)
        await db.commit()

        # Summary
        total_r = sum([4, 4, 3, 6, 4, 3, 3, 3, 3])
        print(f"\nSeeded successfully!")
        print(f"  IeltsTest:     {ielts.id}")
        print(f"  ListeningTest: {lt.id}  (4 sections, 12 questions)")
        print(f"  ReadingTest:   {rt.id}  (3 passages, {total_r} questions)")
        print(f"\nCopy the IeltsTest ID — you'll need it for testing.")


if __name__ == "__main__":
    asyncio.run(seed())
