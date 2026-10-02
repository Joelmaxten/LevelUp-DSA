"""
Career Discovery quiz data: the 15 CS career paths, the 18-question bank,
and the option-to-career-signal mapping. Pure data — no logic here.
"""

from app.pipeline.career_path_registry import CAREER_PATHS

QUESTIONS = {
    "Q1": {
        "text": "What kind of activity naturally keeps you engaged for a long time?",
        "options": {
            "A": "Solving puzzles, logical problems, or figuring out how something works",
            "B": "Creating something — designs, videos, stories, apps, art, etc.",
            "C": "Exploring information, finding patterns, researching, or discovering new things",
            "D": "Helping, teaching, communicating, or working with people",
        },
    },
    "Q2": {
        "text": "Imagine you are given a completely unfamiliar problem. What do you naturally do first?",
        "options": {
            "A": "Break it into smaller parts and solve it step by step",
            "B": "Search for examples and learn how others solved similar problems",
            "C": "Experiment with different ideas until something works",
            "D": "Discuss it with others and combine different viewpoints",
        },
    },
    "Q3": {
        "text": "Which type of challenge sounds most exciting to you?",
        "options": {
            "A": "Finding patterns in a large amount of information",
            "B": "Building something that people can actually use",
            "C": "Finding weaknesses, solving mysteries, or figuring out why something went wrong",
            "D": "Designing a new experience, product, story, or visual idea",
        },
    },
    "Q4": {
        "text": "Which of these would you most enjoy doing in your free time?",
        "options": {
            "A": "Playing strategy games, solving puzzles, coding, or exploring technology",
            "B": "Drawing, editing, photography, music, writing, gaming creatively, or designing",
            "C": "Watching documentaries, researching interesting topics, reading, experimenting",
            "D": "Sports, social activities, leadership, volunteering, teaching, or organizing events",
        },
    },
    "Q5": {
        "text": "Which statement sounds most like you?",
        "options": {
            "A": "I want to understand how and why things work.",
            "B": "I want to create something new.",
            "C": "I want to solve difficult problems.",
            "D": "I want to make an impact on people.",
        },
    },
    "Q6": {
        "text": "Suppose you have one month to learn something completely new. What would attract you most?",
        "options": {
            "A": "Programming, AI, robotics, cybersecurity, or technology",
            "B": "Design, animation, video, music, writing, or creative tools",
            "C": "Psychology, science, mathematics, finance, or research",
            "D": "Business, communication, leadership, marketing, or entrepreneurship",
        },
    },
    "Q7": {
        "text": "When you succeed at something difficult, what feels most satisfying?",
        "options": {
            "A": "I figured out something that seemed impossible.",
            "B": "I created something that did not exist before.",
            "C": "I discovered something others had not noticed.",
            "D": "I helped someone or achieved something together with others.",
        },
    },
    "Q8": {
        "text": "What kind of work environment sounds most comfortable to you?",
        "options": {
            "A": "Quiet, focused work where I can think deeply on my own",
            "B": "A creative environment where I can experiment freely",
            "C": "A team where people discuss ideas and solve problems together",
            "D": "A fast-moving environment with leadership, competition, and changing challenges",
        },
    },
    "Q9": {
        "text": "Which kind of problem would you be most willing to spend hours solving?",
        "options": {
            "A": "A complex technical problem with no obvious solution",
            "B": "A problem where I need to understand people and their needs",
            "C": "A problem involving data, patterns, predictions, or evidence",
            "D": "A problem requiring a completely original or creative solution",
        },
    },
    "Q10": {
        "text": "Imagine you are successful 10 years from now. Which achievement would make you most proud?",
        "options": {
            "A": "I built an important technology, product, or system.",
            "B": "I became highly skilled in a field and discovered or created something valuable.",
            "C": "I built a successful business, led people, or created significant impact.",
            "D": "I created work that people remember, use, enjoy, or connect with.",
        },
    },
    "Q11": {
        "text": "Your college is making a new app for students. Which task would you pick first?",
        "options": {
            "A": "Talk to students and draw rough screens to show how the app should feel to use",
            "B": "Write the code that makes the screens open fast and look right on every phone",
            "C": "Set up the server and database so thousands of students can use the app at once",
            "D": "Try to break the app in every way you can, so problems are found before students see them",
        },
    },
    "Q12": {
        "text": "A shop has years of sales and customer records. What would you most like to do with them?",
        "options": {
            "A": "Build a tool that guesses which customers might stop buying next month",
            "B": "Make simple charts and a weekly report that tell the owner what is selling well",
            "C": "Write the program that gathers the records from many places and keeps them clean every day",
            "D": "Find out why sales dropped last month by comparing numbers across cities and months",
        },
    },
    "Q13": {
        "text": "A website you built becomes slow and sometimes stops working when many people visit. What do you do first?",
        "options": {
            "A": "Add more servers, spread the visitors across them, and keep an eye on the monthly cost",
            "B": "Set up an automatic process that tests and releases fixes quickly and warns the team when something breaks",
            "C": "Read the code, find the slow part, and rewrite it",
            "D": "Check whether someone is sending fake visits on purpose to bring the site down",
        },
    },
    "Q14": {
        "text": "A company wants to add a smart AI helper to its app. Which part sounds most interesting?",
        "options": {
            "A": "Connect a ready-made AI tool to the app and decide how it should talk to users",
            "B": "Collect examples and train the helper yourself so it gets better at one job",
            "C": "Check the helper's answers for mistakes and unsafe replies",
            "D": "Design the chat screen so it is simple and pleasant to use",
        },
    },
    "Q15": {
        "text": "In a group project, what do you usually end up doing?",
        "options": {
            "A": "Checking everyone's work carefully and writing down what does not work",
            "B": "Making sure the project runs the same way on every laptop and still works after each change",
            "C": "Collecting and tidying all the data the team needs",
            "D": "Writing the main logic that decides how the program behaves",
        },
    },
    "Q16": {
        "text": "Which project would you be proudest to show in an interview?",
        "options": {
            "A": "A game where players solve puzzles to unlock new levels",
            "B": "A phone app that people use every day",
            "C": "A tool that checks a small network and reports where it is weak",
            "D": "A page that turns raw numbers into clear answers for a manager",
        },
    },
    "Q17": {
        "text": "You have a free weekend. Which would you pick?",
        "options": {
            "A": "Learn how websites are kept safe and try a practice challenge",
            "B": "Turn a design into a working web page that looks good on both phone and laptop",
            "C": "Ask three people how they use an app and sketch ideas to fix what annoys them",
            "D": "Rent a small server on the internet and set up storage and networking so a project can run there",
        },
    },
    "Q18": {
        "text": "Which data task would you choose for a week?",
        "options": {
            "A": "Build a tool that predicts house prices from old sales, then check how wrong it is",
            "B": "Answer a manager's question like \"Which product sold best?\" using sheets and charts",
            "C": "Build the system that moves data from many apps into one place every night",
            "D": "Check whether a new feature really made more people sign up",
        },
    },
}

# HOW OPTIONS MAP TO CAREER PATHS (read this before editing):
# Every (question, option) below lists the 1 to 3 career paths that option points toward. This
# mapping is HAND-AUTHORED JUDGMENT, not derived from data: nobody measured what students who
# became (say) a DevOps engineer actually answered. It encodes a reasonable guess about which kind
# of work each answer suggests, written so that
#   - no option signals more than 3 paths, and every path has at least 6 options pointing to it
#     (including QA & Test Automation, Data Engineering, Cloud Engineering and DevOps, which the
#     first version of the quiz could never reach);
#   - each pair listed in career_path_registry.PATH_PAIRS (AI/ML, Data Science/Data Analytics,
#     Cloud/DevOps, UI-UX/Frontend) has at least 2 options that point to ONLY ONE of the pair, for
#     each side - those options are what lets the quiz tell the two apart;
#   - the original ten questions (Q1-Q10) keep their wording and meaning; only their signals were
#     rewritten (see docs/PROJECT_BIOGRAPHY.md's "Quiz Redesign" entry for the list of changes).
# Q11-Q18 are the scenario questions added in the redesign. Changing any signal changes quiz
# results: re-run scripts/smoke_test_quiz.py and recapture the golden file on purpose
# (docs/DEV_SETUP.md says how).
OPTION_SIGNALS = {
    ("Q1", "A"): ["Backend Engineering", "Cybersecurity", "Machine Learning Engineering"],
    ("Q1", "B"): ["UI/UX Design", "Game Development", "Mobile App Development"],
    ("Q1", "C"): ["Data Science", "Data Analytics", "Cybersecurity"],
    ("Q1", "D"): ["UI/UX Design", "Frontend Development"],

    ("Q2", "A"): ["Backend Engineering", "Data Engineering", "QA & Test Automation"],
    ("Q2", "B"): ["Full-Stack Development", "Data Analytics", "Cloud Engineering"],
    ("Q2", "C"): ["AI Engineering", "Game Development", "Full-Stack Development"],
    ("Q2", "D"): ["UI/UX Design", "Full-Stack Development", "DevOps"],

    ("Q3", "A"): ["Data Science", "Data Analytics", "Data Engineering"],
    ("Q3", "B"): ["Full-Stack Development", "Mobile App Development", "Frontend Development"],
    ("Q3", "C"): ["Cybersecurity", "QA & Test Automation", "DevOps"],
    ("Q3", "D"): ["UI/UX Design", "Game Development"],

    ("Q4", "A"): ["Full-Stack Development", "Game Development", "Cybersecurity"],
    ("Q4", "B"): ["UI/UX Design", "Game Development"],
    ("Q4", "C"): ["AI Engineering", "Data Science", "Cybersecurity"],
    ("Q4", "D"): ["DevOps", "QA & Test Automation"],

    ("Q5", "A"): ["Machine Learning Engineering", "Cybersecurity", "Data Science"],
    ("Q5", "B"): ["Full-Stack Development", "Game Development", "UI/UX Design"],
    ("Q5", "C"): ["AI Engineering", "Backend Engineering", "Cybersecurity"],
    ("Q5", "D"): ["UI/UX Design", "Frontend Development", "Mobile App Development"],

    ("Q6", "A"): ["AI Engineering", "Cybersecurity", "Backend Engineering"],
    ("Q6", "B"): ["UI/UX Design", "Game Development"],
    ("Q6", "C"): ["Data Science", "Machine Learning Engineering"],
    ("Q6", "D"): ["Data Analytics", "Full-Stack Development", "Mobile App Development"],

    ("Q7", "A"): ["Machine Learning Engineering", "Cybersecurity", "Backend Engineering"],
    ("Q7", "B"): ["Full-Stack Development", "Game Development", "Mobile App Development"],
    ("Q7", "C"): ["Data Science", "Cybersecurity", "QA & Test Automation"],
    ("Q7", "D"): ["UI/UX Design", "Frontend Development", "DevOps"],

    ("Q8", "A"): ["Backend Engineering", "Data Engineering", "Machine Learning Engineering"],
    ("Q8", "B"): ["UI/UX Design", "Game Development", "Frontend Development"],
    ("Q8", "C"): ["Full-Stack Development", "DevOps", "Cloud Engineering"],
    ("Q8", "D"): ["Cybersecurity", "Cloud Engineering"],

    ("Q9", "A"): ["Backend Engineering", "Cloud Engineering", "Machine Learning Engineering"],
    ("Q9", "B"): ["UI/UX Design", "Frontend Development", "QA & Test Automation"],
    ("Q9", "C"): ["Data Science", "Data Analytics", "Machine Learning Engineering"],
    ("Q9", "D"): ["Game Development", "AI Engineering", "Full-Stack Development"],

    ("Q10", "A"): ["Backend Engineering", "Cloud Engineering", "Full-Stack Development"],
    ("Q10", "B"): ["AI Engineering", "Data Science", "Cybersecurity"],
    ("Q10", "C"): ["Full-Stack Development", "Data Analytics", "DevOps"],
    ("Q10", "D"): ["UI/UX Design", "Game Development", "Mobile App Development"],

    ("Q11", "A"): ["UI/UX Design"],
    ("Q11", "B"): ["Frontend Development", "Mobile App Development"],
    ("Q11", "C"): ["Backend Engineering", "Cloud Engineering"],
    ("Q11", "D"): ["QA & Test Automation"],

    ("Q12", "A"): ["Data Science", "Machine Learning Engineering"],
    ("Q12", "B"): ["Data Analytics"],
    ("Q12", "C"): ["Data Engineering", "Backend Engineering"],
    ("Q12", "D"): ["Data Analytics", "Data Science"],

    ("Q13", "A"): ["Cloud Engineering"],
    ("Q13", "B"): ["DevOps"],
    ("Q13", "C"): ["Backend Engineering", "Frontend Development"],
    ("Q13", "D"): ["Cybersecurity"],

    ("Q14", "A"): ["AI Engineering", "Full-Stack Development"],
    ("Q14", "B"): ["Machine Learning Engineering"],
    ("Q14", "C"): ["QA & Test Automation", "Cybersecurity", "AI Engineering"],
    ("Q14", "D"): ["UI/UX Design", "Frontend Development"],

    ("Q15", "A"): ["QA & Test Automation"],
    ("Q15", "B"): ["DevOps"],
    ("Q15", "C"): ["Data Engineering", "Data Analytics"],
    ("Q15", "D"): ["Backend Engineering", "Full-Stack Development"],

    ("Q16", "A"): ["Game Development"],
    ("Q16", "B"): ["Mobile App Development", "Full-Stack Development"],
    ("Q16", "C"): ["Cybersecurity"],
    ("Q16", "D"): ["Data Analytics"],

    ("Q17", "A"): ["Cybersecurity"],
    ("Q17", "B"): ["Frontend Development", "Full-Stack Development"],
    ("Q17", "C"): ["UI/UX Design"],
    ("Q17", "D"): ["Cloud Engineering"],

    ("Q18", "A"): ["Data Science", "Machine Learning Engineering"],
    ("Q18", "B"): ["Data Analytics"],
    ("Q18", "C"): ["Data Engineering"],
    ("Q18", "D"): ["Data Analytics", "Data Science"],
}
