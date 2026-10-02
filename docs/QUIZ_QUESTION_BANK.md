# Career quiz question bank (after the redesign)

Generated from `app/pipeline/career_quiz_data.py` and the original bank at commit 4505662. The option-to-path
mapping is hand-authored judgment, not derived from data. Regenerate this file if the bank changes.

## New questions (Q11-Q18)

**Q11. Your college is making a new app for students. Which task would you pick first?**

- A. Talk to students and draw rough screens to show how the app should feel to use → UI/UX Design
- B. Write the code that makes the screens open fast and look right on every phone → Frontend Development, Mobile App Development
- C. Set up the server and database so thousands of students can use the app at once → Backend Engineering, Cloud Engineering
- D. Try to break the app in every way you can, so problems are found before students see them → QA & Test Automation

**Q12. A shop has years of sales and customer records. What would you most like to do with them?**

- A. Build a tool that guesses which customers might stop buying next month → Data Science, Machine Learning Engineering
- B. Make simple charts and a weekly report that tell the owner what is selling well → Data Analytics
- C. Write the program that gathers the records from many places and keeps them clean every day → Data Engineering, Backend Engineering
- D. Find out why sales dropped last month by comparing numbers across cities and months → Data Analytics, Data Science

**Q13. A website you built becomes slow and sometimes stops working when many people visit. What do you do first?**

- A. Add more servers, spread the visitors across them, and keep an eye on the monthly cost → Cloud Engineering
- B. Set up an automatic process that tests and releases fixes quickly and warns the team when something breaks → DevOps
- C. Read the code, find the slow part, and rewrite it → Backend Engineering, Frontend Development
- D. Check whether someone is sending fake visits on purpose to bring the site down → Cybersecurity

**Q14. A company wants to add a smart AI helper to its app. Which part sounds most interesting?**

- A. Connect a ready-made AI tool to the app and decide how it should talk to users → AI Engineering, Full-Stack Development
- B. Collect examples and train the helper yourself so it gets better at one job → Machine Learning Engineering
- C. Check the helper's answers for mistakes and unsafe replies → QA & Test Automation, Cybersecurity, AI Engineering
- D. Design the chat screen so it is simple and pleasant to use → UI/UX Design, Frontend Development

**Q15. In a group project, what do you usually end up doing?**

- A. Checking everyone's work carefully and writing down what does not work → QA & Test Automation
- B. Making sure the project runs the same way on every laptop and still works after each change → DevOps
- C. Collecting and tidying all the data the team needs → Data Engineering, Data Analytics
- D. Writing the main logic that decides how the program behaves → Backend Engineering, Full-Stack Development

**Q16. Which project would you be proudest to show in an interview?**

- A. A game where players solve puzzles to unlock new levels → Game Development
- B. A phone app that people use every day → Mobile App Development, Full-Stack Development
- C. A tool that checks a small network and reports where it is weak → Cybersecurity
- D. A page that turns raw numbers into clear answers for a manager → Data Analytics

**Q17. You have a free weekend. Which would you pick?**

- A. Learn how websites are kept safe and try a practice challenge → Cybersecurity
- B. Turn a design into a working web page that looks good on both phone and laptop → Frontend Development, Full-Stack Development
- C. Ask three people how they use an app and sketch ideas to fix what annoys them → UI/UX Design
- D. Rent a small server on the internet and set up storage and networking so a project can run there → Cloud Engineering

**Q18. Which data task would you choose for a week?**

- A. Build a tool that predicts house prices from old sales, then check how wrong it is → Data Science, Machine Learning Engineering
- B. Answer a manager's question like "Which product sold best?" using sheets and charts → Data Analytics
- C. Build the system that moves data from many apps into one place every night → Data Engineering
- D. Check whether a new feature really made more people sign up → Data Analytics, Data Science

## Original questions (Q1-Q10): wording unchanged, signals rewritten

Each option signals at most 3 paths now (it was up to 6), the three options that signalled nothing now signal something,
and every pair of split paths gets distinct signals. Old → new for every option (an option marked *same* kept its signals):

**Q1. What kind of activity naturally keeps you engaged for a long time?**

- A. Solving puzzles, logical problems, or figuring out how something works
  - old: Full-Stack Development, Backend Engineering, AI Engineering, Machine Learning Engineering, Cybersecurity
  - new: Backend Engineering, Cybersecurity, Machine Learning Engineering
- B. Creating something — designs, videos, stories, apps, art, etc.
  - old: UI/UX Design, Frontend Development, Game Development, Mobile App Development
  - new: UI/UX Design, Game Development, Mobile App Development
- C. Exploring information, finding patterns, researching, or discovering new things
  - old: Data Science, Data Analytics, AI Engineering, Machine Learning Engineering, Cybersecurity
  - new: Data Science, Data Analytics, Cybersecurity
- D. Helping, teaching, communicating, or working with people → *same:* UI/UX Design, Frontend Development

**Q2. Imagine you are given a completely unfamiliar problem. What do you naturally do first?**

- A. Break it into smaller parts and solve it step by step
  - old: Full-Stack Development, Backend Engineering, AI Engineering, Machine Learning Engineering, Cybersecurity
  - new: Backend Engineering, Data Engineering, QA & Test Automation
- B. Search for examples and learn how others solved similar problems
  - old: Full-Stack Development, Data Science, Data Analytics, Cloud Engineering, DevOps
  - new: Full-Stack Development, Data Analytics, Cloud Engineering
- C. Experiment with different ideas until something works
  - old: AI Engineering, Machine Learning Engineering, Game Development, Full-Stack Development
  - new: AI Engineering, Game Development, Full-Stack Development
- D. Discuss it with others and combine different viewpoints
  - old: UI/UX Design, Frontend Development, Full-Stack Development
  - new: UI/UX Design, Full-Stack Development, DevOps

**Q3. Which type of challenge sounds most exciting to you?**

- A. Finding patterns in a large amount of information
  - old: Data Science, Data Analytics, AI Engineering, Machine Learning Engineering
  - new: Data Science, Data Analytics, Data Engineering
- B. Building something that people can actually use
  - old: Full-Stack Development, Mobile App Development, Backend Engineering
  - new: Full-Stack Development, Mobile App Development, Frontend Development
- C. Finding weaknesses, solving mysteries, or figuring out why something went wrong
  - old: Cybersecurity
  - new: Cybersecurity, QA & Test Automation, DevOps
- D. Designing a new experience, product, story, or visual idea
  - old: UI/UX Design, Frontend Development, Game Development
  - new: UI/UX Design, Game Development

**Q4. Which of these would you most enjoy doing in your free time?**

- A. Playing strategy games, solving puzzles, coding, or exploring technology
  - old: Full-Stack Development, AI Engineering, Machine Learning Engineering, Cybersecurity, Game Development
  - new: Full-Stack Development, Game Development, Cybersecurity
- B. Drawing, editing, photography, music, writing, gaming creatively, or designing
  - old: UI/UX Design, Frontend Development, Game Development, Mobile App Development
  - new: UI/UX Design, Game Development
- C. Watching documentaries, researching interesting topics, reading, experimenting
  - old: AI Engineering, Machine Learning Engineering, Data Science, Data Analytics, Cybersecurity
  - new: AI Engineering, Data Science, Cybersecurity
- D. Sports, social activities, leadership, volunteering, teaching, or organizing events
  - old: (none)
  - new: DevOps, QA & Test Automation

**Q5. Which statement sounds most like you?**

- A. I want to understand how and why things work.
  - old: Backend Engineering, AI Engineering, Machine Learning Engineering, Cybersecurity
  - new: Machine Learning Engineering, Cybersecurity, Data Science
- B. I want to create something new.
  - old: Full-Stack Development, Mobile App Development, Game Development, UI/UX Design, Frontend Development
  - new: Full-Stack Development, Game Development, UI/UX Design
- C. I want to solve difficult problems.
  - old: AI Engineering, Machine Learning Engineering, Full-Stack Development, Cybersecurity
  - new: AI Engineering, Backend Engineering, Cybersecurity
- D. I want to make an impact on people.
  - old: UI/UX Design, Frontend Development
  - new: UI/UX Design, Frontend Development, Mobile App Development

**Q6. Suppose you have one month to learn something completely new. What would attract you most?**

- A. Programming, AI, robotics, cybersecurity, or technology
  - old: Full-Stack Development, AI Engineering, Machine Learning Engineering, Cybersecurity
  - new: AI Engineering, Cybersecurity, Backend Engineering
- B. Design, animation, video, music, writing, or creative tools
  - old: UI/UX Design, Frontend Development, Game Development
  - new: UI/UX Design, Game Development
- C. Psychology, science, mathematics, finance, or research
  - old: Data Science, Data Analytics, AI Engineering, Machine Learning Engineering
  - new: Data Science, Machine Learning Engineering
- D. Business, communication, leadership, marketing, or entrepreneurship
  - old: (none)
  - new: Data Analytics, Full-Stack Development, Mobile App Development

**Q7. When you succeed at something difficult, what feels most satisfying?**

- A. I figured out something that seemed impossible.
  - old: AI Engineering, Machine Learning Engineering, Full-Stack Development, Cybersecurity, Backend Engineering
  - new: Machine Learning Engineering, Cybersecurity, Backend Engineering
- B. I created something that did not exist before.
  - old: Full-Stack Development, Mobile App Development, Game Development, UI/UX Design, Frontend Development
  - new: Full-Stack Development, Game Development, Mobile App Development
- C. I discovered something others had not noticed.
  - old: Data Science, Data Analytics, AI Engineering, Machine Learning Engineering, Cybersecurity
  - new: Data Science, Cybersecurity, QA & Test Automation
- D. I helped someone or achieved something together with others.
  - old: UI/UX Design, Frontend Development
  - new: UI/UX Design, Frontend Development, DevOps

**Q8. What kind of work environment sounds most comfortable to you?**

- A. Quiet, focused work where I can think deeply on my own
  - old: Backend Engineering, AI Engineering, Machine Learning Engineering, Data Science, Data Analytics
  - new: Backend Engineering, Data Engineering, Machine Learning Engineering
- B. A creative environment where I can experiment freely
  - old: UI/UX Design, Frontend Development, Game Development, Mobile App Development
  - new: UI/UX Design, Game Development, Frontend Development
- C. A team where people discuss ideas and solve problems together
  - old: Full-Stack Development, Cloud Engineering, DevOps
  - new: Full-Stack Development, DevOps, Cloud Engineering
- D. A fast-moving environment with leadership, competition, and changing challenges
  - old: Cybersecurity, Cloud Engineering, DevOps
  - new: Cybersecurity, Cloud Engineering

**Q9. Which kind of problem would you be most willing to spend hours solving?**

- A. A complex technical problem with no obvious solution
  - old: Full-Stack Development, Backend Engineering, AI Engineering, Machine Learning Engineering, Cloud Engineering, DevOps
  - new: Backend Engineering, Cloud Engineering, Machine Learning Engineering
- B. A problem where I need to understand people and their needs
  - old: UI/UX Design, Frontend Development
  - new: UI/UX Design, Frontend Development, QA & Test Automation
- C. A problem involving data, patterns, predictions, or evidence
  - old: Data Science, Data Analytics, AI Engineering, Machine Learning Engineering
  - new: Data Science, Data Analytics, Machine Learning Engineering
- D. A problem requiring a completely original or creative solution
  - old: AI Engineering, Machine Learning Engineering, Game Development, Full-Stack Development
  - new: Game Development, AI Engineering, Full-Stack Development

**Q10. Imagine you are successful 10 years from now. Which achievement would make you most proud?**

- A. I built an important technology, product, or system.
  - old: Full-Stack Development, Backend Engineering, Cloud Engineering, DevOps, AI Engineering, Machine Learning Engineering
  - new: Backend Engineering, Cloud Engineering, Full-Stack Development
- B. I became highly skilled in a field and discovered or created something valuable.
  - old: AI Engineering, Machine Learning Engineering, Data Science, Data Analytics, Cybersecurity
  - new: AI Engineering, Data Science, Cybersecurity
- C. I built a successful business, led people, or created significant impact.
  - old: (none)
  - new: Full-Stack Development, Data Analytics, DevOps
- D. I created work that people remember, use, enjoy, or connect with.
  - old: UI/UX Design, Frontend Development, Game Development, Mobile App Development
  - new: UI/UX Design, Game Development, Mobile App Development
