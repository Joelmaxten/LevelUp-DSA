"""
Career Discovery quiz data: the 10 CS career paths, the 10-question bank,
and the option-to-career-signal mapping. Pure data — no logic here.
"""

CAREER_PATHS = [
    "Software Engineering / Full-Stack Development",
    "AI / Machine Learning Engineering",
    "Data Science / Data Analytics",
    "Cybersecurity",
    "Cloud / DevOps",
    "Mobile App Development",
    "Game Development",
    "UI/UX + Frontend Development",
    "Backend / Systems Engineering",
    "Research / Advanced Computing",
]

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
}

# Each (question, option) maps to a list of career paths it signals support for.
OPTION_SIGNALS = {
    ("Q1", "A"): ["Software Engineering / Full-Stack Development", "Backend / Systems Engineering", "AI / Machine Learning Engineering", "Cybersecurity", "Research / Advanced Computing"],
    ("Q1", "B"): ["UI/UX + Frontend Development", "Game Development", "Mobile App Development"],
    ("Q1", "C"): ["Data Science / Data Analytics", "AI / Machine Learning Engineering", "Research / Advanced Computing", "Cybersecurity"],
    ("Q1", "D"): ["UI/UX + Frontend Development"],

    ("Q2", "A"): ["Software Engineering / Full-Stack Development", "Backend / Systems Engineering", "AI / Machine Learning Engineering", "Cybersecurity"],
    ("Q2", "B"): ["Software Engineering / Full-Stack Development", "Data Science / Data Analytics", "Cloud / DevOps"],
    ("Q2", "C"): ["AI / Machine Learning Engineering", "Game Development", "Research / Advanced Computing", "Software Engineering / Full-Stack Development"],
    ("Q2", "D"): ["UI/UX + Frontend Development", "Software Engineering / Full-Stack Development"],

    ("Q3", "A"): ["Data Science / Data Analytics", "AI / Machine Learning Engineering"],
    ("Q3", "B"): ["Software Engineering / Full-Stack Development", "Mobile App Development", "Backend / Systems Engineering"],
    ("Q3", "C"): ["Cybersecurity"],
    ("Q3", "D"): ["UI/UX + Frontend Development", "Game Development"],

    ("Q4", "A"): ["Software Engineering / Full-Stack Development", "AI / Machine Learning Engineering", "Cybersecurity", "Game Development"],
    ("Q4", "B"): ["UI/UX + Frontend Development", "Game Development", "Mobile App Development"],
    ("Q4", "C"): ["AI / Machine Learning Engineering", "Data Science / Data Analytics", "Research / Advanced Computing", "Cybersecurity"],
    ("Q4", "D"): ["Research / Advanced Computing"],

    ("Q5", "A"): ["Backend / Systems Engineering", "AI / Machine Learning Engineering", "Cybersecurity", "Research / Advanced Computing"],
    ("Q5", "B"): ["Software Engineering / Full-Stack Development", "Mobile App Development", "Game Development", "UI/UX + Frontend Development"],
    ("Q5", "C"): ["AI / Machine Learning Engineering", "Software Engineering / Full-Stack Development", "Cybersecurity", "Research / Advanced Computing"],
    ("Q5", "D"): ["UI/UX + Frontend Development"],

    ("Q6", "A"): ["Software Engineering / Full-Stack Development", "AI / Machine Learning Engineering", "Cybersecurity"],
    ("Q6", "B"): ["UI/UX + Frontend Development", "Game Development"],
    ("Q6", "C"): ["Data Science / Data Analytics", "AI / Machine Learning Engineering", "Research / Advanced Computing"],
    ("Q6", "D"): ["Research / Advanced Computing"],

    ("Q7", "A"): ["AI / Machine Learning Engineering", "Software Engineering / Full-Stack Development", "Cybersecurity", "Backend / Systems Engineering"],
    ("Q7", "B"): ["Software Engineering / Full-Stack Development", "Mobile App Development", "Game Development", "UI/UX + Frontend Development"],
    ("Q7", "C"): ["Data Science / Data Analytics", "AI / Machine Learning Engineering", "Cybersecurity", "Research / Advanced Computing"],
    ("Q7", "D"): ["UI/UX + Frontend Development"],

    ("Q8", "A"): ["Backend / Systems Engineering", "AI / Machine Learning Engineering", "Data Science / Data Analytics", "Research / Advanced Computing"],
    ("Q8", "B"): ["UI/UX + Frontend Development", "Game Development", "Mobile App Development"],
    ("Q8", "C"): ["Software Engineering / Full-Stack Development", "Cloud / DevOps"],
    ("Q8", "D"): ["Cybersecurity", "Cloud / DevOps"],

    ("Q9", "A"): ["Software Engineering / Full-Stack Development", "Backend / Systems Engineering", "AI / Machine Learning Engineering", "Cloud / DevOps"],
    ("Q9", "B"): ["UI/UX + Frontend Development"],
    ("Q9", "C"): ["Data Science / Data Analytics", "AI / Machine Learning Engineering"],
    ("Q9", "D"): ["AI / Machine Learning Engineering", "Game Development", "Software Engineering / Full-Stack Development", "Research / Advanced Computing"],

    ("Q10", "A"): ["Software Engineering / Full-Stack Development", "Backend / Systems Engineering", "Cloud / DevOps", "AI / Machine Learning Engineering"],
    ("Q10", "B"): ["AI / Machine Learning Engineering", "Data Science / Data Analytics", "Research / Advanced Computing", "Cybersecurity"],
    ("Q10", "C"): ["Research / Advanced Computing"],
    ("Q10", "D"): ["UI/UX + Frontend Development", "Game Development", "Mobile App Development"],
}