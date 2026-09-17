"""
seed_database.py
-------------------
Populates the database with sample data for testing/demo purposes.
Module 5 Part 19 (initial version) -> Module 6 Part 14 (invigilator +
sample sessions) -> Module 7 Part 1/2 (this version): three named,
professional candidate-facing assessments, and a much broader
question bank across 8 categories.

Creates:
  - Three ACTIVE, candidate-facing assessments, exactly as specified:
    "Python Programming Basics" (30 min, 10 Q, 12 marks to pass),
    "Artificial Intelligence Fundamentals" (20 min, 8 Q), and
    "Aptitude Assessment" (15 min, 10 Q) — all with monitoring enabled.
  - Five INACTIVE "question bank" assessments (Data Structures, DBMS,
    Operating Systems, Computer Networks, OOP) holding real, curated
    questions in those categories. They're marked `is_active=False` so
    they never appear on the candidate-facing /assessment/ list (Part
    1 explicitly wants exactly the three assessments above to show
    there) — this is a deliberate, documented design choice rather
    than a schema change: `Question.assessment_id` is a required
    foreign key (see models/assessment.py), so a true
    assessment-agnostic "question bank" would need a many-to-many
    schema change, which is out of scope for a content-seeding task.
    Marking these five as inactive containers is the smallest change
    that satisfies "populate a question bank across 8 categories"
    without touching a working data model.
  - Every question is real, curated, professional content — NOT
    Faker-generated or placeholder text, per Module 7's explicit
    instruction. All 58 questions across the 8 categories were written
    for this seed script specifically.
  - One invigilator account (invigilator@proctoriq.test / password123).
  - A configurable number of dummy candidate accounts (Faker — used
    only for filler names/emails, never for question content).
  - A handful of sample AssessmentSession rows so the invigilator
    dashboard, Violations, and Analytics pages have real data.

Usage:
    python3 seed_database.py                  # seed everything with defaults
    python3 seed_database.py --candidates 20   # more dummy candidates
    python3 seed_database.py --no-candidates   # skip dummy candidates
    python3 seed_database.py --no-sessions      # skip sample sessions

Safe to re-run: skips creating any assessment that already exists (by
name), so it won't create duplicates. Re-running WILL add another
batch of sample sessions each time, though.
"""

import argparse
import random
import sys

from app import create_app
from models import db
from models.user import User
from models.assessment import Assessment, Question, Option


# ---------------------------------------------------------------------
# Question bank content
# ---------------------------------------------------------------------
# Each question tuple: (text, marks, category, difficulty, [(option_text, is_correct), ...])

PYTHON_QUESTIONS = [
    ("What is the output of `type([])` in Python?", 1.0, "Python", "Easy",
     [("<class 'list'>", True), ("<class 'array'>", False), ("<class 'tuple'>", False), ("<class 'dict'>", False)]),
    ("Which keyword is used to define a function in Python?", 1.0, "Python", "Easy",
     [("func", False), ("def", True), ("function", False), ("lambda", False)]),
    ("What does the `len()` function return when called on a string?", 2.0, "Python", "Medium",
     [("The memory size of the string", False), ("The number of characters in the string", True),
      ("The ASCII value of the first character", False), ("The number of words in the string", False)]),
    ("Which construct is used to handle exceptions in Python?", 2.0, "Python", "Medium",
     [("catch/throw", False), ("try/except", True), ("do/catch", False), ("error/handle", False)]),
    ("What is the result of the expression `3 // 2` in Python?", 3.0, "Python", "Hard",
     [("1.5", False), ("1", True), ("2", False), ("0", False)]),
    ("Which of the following built-in Python data types is immutable?", 1.0, "Python", "Easy",
     [("list", False), ("dict", False), ("tuple", True), ("set", False)]),
    ("In a Python instance method, what does the first parameter `self` refer to?", 2.0, "Python", "Medium",
     [("The class itself", False), ("The instance the method is called on", True),
      ("The parent class", False), ("A required global variable", False)]),
    ("Which statement immediately exits the nearest enclosing loop in Python?", 3.0, "Python", "Hard",
     [("continue", False), ("pass", False), ("break", True), ("return", False)]),
    ("What is the primary purpose of a list comprehension in Python?", 2.0, "Python", "Medium",
     [("To sort a list in place", False), ("To concisely build a new list from an iterable", True),
      ("To convert a list into a dictionary", False), ("To delete elements from a list", False)]),
    ("Which standard library module provides support for regular expressions in Python?", 3.0, "Python", "Hard",
     [("regex", False), ("string", False), ("re", True), ("pattern", False)]),
]  # total marks = 20

AI_QUESTIONS = [
    ("What does the abbreviation 'AI' stand for?", 1.0, "Artificial Intelligence", "Easy",
     [("Automated Interface", False), ("Artificial Intelligence", True), ("Applied Informatics", False), ("Algorithmic Iteration", False)]),
    ("Which of the following is an example of a supervised learning algorithm?", 1.0, "Artificial Intelligence", "Easy",
     [("K-Means Clustering", False), ("Linear Regression", True), ("Apriori Algorithm", False), ("Principal Component Analysis", False)]),
    ("What is the primary goal of a machine learning model during training?", 1.0, "Artificial Intelligence", "Easy",
     [("To memorize the training data exactly", False),
      ("To learn patterns from data so it can make predictions on new data", True),
      ("To reduce the size of the dataset", False), ("To encrypt the training data", False)]),
    ("Which of the following is a common unsupervised learning technique?", 2.0, "Artificial Intelligence", "Medium",
     [("K-Means Clustering", True), ("Logistic Regression", False), ("Decision Tree Classification", False), ("Support Vector Machines", False)]),
    ("In machine learning, what does 'training data' refer to?", 2.0, "Artificial Intelligence", "Medium",
     [("Data reserved only for final evaluation", False), ("Data used to teach a model to recognize patterns", True),
      ("Randomly generated noise added to a dataset", False), ("The model's output predictions", False)]),
    ("Which neural network architecture is most commonly used for image recognition tasks?", 1.0, "Artificial Intelligence", "Easy",
     [("Recurrent Neural Network (RNN)", False), ("Convolutional Neural Network (CNN)", True),
      ("Generative Adversarial Network (GAN)", False), ("Radial Basis Function Network", False)]),
    ("What is 'overfitting' in the context of machine learning?", 2.0, "Artificial Intelligence", "Medium",
     [("The model performs well on training data but poorly on unseen data", True),
      ("The model takes too long to train", False),
      ("The model has too few parameters to learn effectively", False),
      ("The model requires too much memory to run", False)]),
    ("Which of the following best describes Natural Language Processing (NLP)?", 2.0, "Artificial Intelligence", "Medium",
     [("A technique for compressing image files", False),
      ("A field enabling computers to understand and process human language", True),
      ("A method for optimizing database queries", False),
      ("A hardware architecture for parallel computing", False)]),
]  # total marks = 12

APTITUDE_QUESTIONS = [
    ("If a train travels 60 km in 45 minutes, what is its speed in km/h?", 1.0, "Aptitude", "Easy",
     [("60 km/h", False), ("80 km/h", True), ("90 km/h", False), ("100 km/h", False)]),
    ("Which number should come next in the series: 2, 6, 12, 20, 30, ?", 1.0, "Aptitude", "Medium",
     [("36", False), ("40", False), ("42", True), ("44", False)]),
    ("Select the word most nearly OPPOSITE in meaning to 'Frugal'.", 1.0, "Aptitude", "Easy",
     [("Thrifty", False), ("Extravagant", True), ("Economical", False), ("Prudent", False)]),
    ("A shopkeeper marks an item 25% above cost price and gives a 10% discount. What is the net profit percentage?", 2.0, "Aptitude", "Hard",
     [("10%", False), ("12.5%", True), ("15%", False), ("25%", False)]),
    ("Which of the following is a prime number?", 1.0, "Aptitude", "Easy",
     [("51", False), ("57", False), ("61", True), ("63", False)]),
    ("'Book' is to 'Read' as 'Song' is to ?", 1.0, "Aptitude", "Easy",
     [("Write", False), ("Sing", True), ("Compose", False), ("Play", False)]),
    ("If CODING is written as DPEJOH, how is FLOWER written in the same code?", 2.0, "Aptitude", "Hard",
     [("GMPXFS", True), ("GMPXES", False), ("HMPXFS", False), ("GNPXFS", False)]),
    ("What is the next number in the sequence: 1, 1, 2, 3, 5, 8, ?", 1.0, "Aptitude", "Medium",
     [("11", False), ("13", True), ("14", False), ("15", False)]),
    ("A is the father of B. B is the sister of C. C is the son of D. How is D related to A?", 2.0, "Aptitude", "Hard",
     [("Wife", True), ("Sister", False), ("Daughter", False), ("Mother", False)]),
    ("Which of the following best describes the purpose of a 'control group' in an experiment?", 1.0, "Aptitude", "Medium",
     [("It receives the treatment being tested", False), ("It provides a baseline for comparison", True),
      ("It is always larger than the test group", False), ("It is used only in medical research", False)]),
]  # total marks = 13

DATA_STRUCTURES_QUESTIONS = [
    ("Which data structure follows First In First Out (FIFO) order?", 1.0, "Data Structures", "Easy",
     [("Stack", False), ("Queue", True), ("Tree", False), ("Graph", False)]),
    ("What is the average-case time complexity of searching in a balanced binary search tree?", 2.0, "Data Structures", "Medium",
     [("O(1)", False), ("O(n)", False), ("O(log n)", True), ("O(n^2)", False)]),
    ("Which data structure is most naturally suited to implementing function call recursion?", 1.0, "Data Structures", "Easy",
     [("Queue", False), ("Stack", True), ("Linked List", False), ("Hash Table", False)]),
    ("In a singly linked list, what does each node typically store?", 1.0, "Data Structures", "Easy",
     [("Only the data value", False), ("Data and a pointer to the next node", True),
      ("Pointers to both the previous and next nodes", False), ("Only a pointer to the head node", False)]),
    ("What is the worst-case time complexity of QuickSort?", 2.0, "Data Structures", "Hard",
     [("O(n log n)", False), ("O(n)", False), ("O(n^2)", True), ("O(log n)", False)]),
    ("Which binary tree traversal visits the left subtree, then the root, then the right subtree?", 2.0, "Data Structures", "Medium",
     [("Pre-order", False), ("Post-order", False), ("In-order", True), ("Level-order", False)]),
]  # total marks = 9

DBMS_QUESTIONS = [
    ("What does the acronym ACID stand for in database transactions?", 2.0, "DBMS", "Medium",
     [("Atomicity, Consistency, Isolation, Durability", True),
      ("Accuracy, Consistency, Integrity, Dependency", False),
      ("Atomicity, Concurrency, Isolation, Data-safety", False),
      ("Availability, Consistency, Isolation, Durability", False)]),
    ("Which SQL clause is used to filter groups after a GROUP BY aggregation?", 2.0, "DBMS", "Medium",
     [("WHERE", False), ("HAVING", True), ("FILTER", False), ("ORDER BY", False)]),
    ("What is a primary key in a relational database table?", 1.0, "DBMS", "Easy",
     [("Any column that stores numeric data", False), ("A column or set of columns that uniquely identifies each row", True),
      ("The first column defined in a table", False), ("A column that allows NULL values", False)]),
    ("Which normal form specifically eliminates transitive dependency?", 3.0, "DBMS", "Hard",
     [("First Normal Form (1NF)", False), ("Second Normal Form (2NF)", False),
      ("Third Normal Form (3NF)", True), ("Boyce-Codd Normal Form (BCNF)", False)]),
    ("Which type of SQL join returns only rows with matching values in both tables?", 1.0, "DBMS", "Easy",
     [("LEFT JOIN", False), ("RIGHT JOIN", False), ("INNER JOIN", True), ("FULL OUTER JOIN", False)]),
    ("What is the main purpose of an index in a database table?", 1.0, "DBMS", "Easy",
     [("To enforce foreign key constraints", False), ("To speed up data retrieval", True),
      ("To automatically back up the table", False), ("To encrypt sensitive columns", False)]),
]  # total marks = 10

OS_QUESTIONS = [
    ("What is a deadlock in an operating system?", 2.0, "Operating Systems", "Medium",
     [("A process that runs forever without terminating", False),
      ("A state where two or more processes are blocked forever, each waiting on the other", True),
      ("A crash caused by insufficient memory", False), ("A scheduling algorithm for real-time systems", False)]),
    ("Which CPU scheduling algorithm can lead to starvation of low-priority processes?", 2.0, "Operating Systems", "Medium",
     [("Round Robin", False), ("First-Come-First-Served", False), ("Priority Scheduling", True), ("Shortest Job First", False)]),
    ("What is the main purpose of virtual memory?", 1.0, "Operating Systems", "Easy",
     [("To make the CPU run faster", False), ("To allow execution of processes larger than physical memory", True),
      ("To permanently store files", False), ("To manage network connections", False)]),
    ("What is a semaphore primarily used for in operating systems?", 2.0, "Operating Systems", "Medium",
     [("File compression", False), ("Process/thread synchronization", True),
      ("Memory defragmentation", False), ("Network packet routing", False)]),
    ("Which of the following is NOT a standard process state?", 1.0, "Operating Systems", "Easy",
     [("Ready", False), ("Waiting", False), ("Compiled", True), ("Running", False)]),
    ("What is 'thrashing' in the context of an operating system?", 3.0, "Operating Systems", "Hard",
     [("A technique for speeding up disk access", False),
      ("Excessive paging that severely degrades system performance", True),
      ("A method of process prioritization", False), ("A type of deadlock recovery", False)]),
]  # total marks = 11

NETWORKS_QUESTIONS = [
    ("Which layer of the OSI model is primarily responsible for routing data between networks?", 2.0, "Computer Networks", "Medium",
     [("Data Link Layer", False), ("Network Layer", True), ("Transport Layer", False), ("Session Layer", False)]),
    ("What does DNS stand for?", 1.0, "Computer Networks", "Easy",
     [("Data Network System", False), ("Domain Name System", True), ("Digital Network Service", False), ("Distributed Naming Server", False)]),
    ("Which transport-layer protocol is connection-oriented?", 1.0, "Computer Networks", "Easy",
     [("UDP", False), ("TCP", True), ("IP", False), ("ICMP", False)]),
    ("What is the default port number used for HTTPS traffic?", 2.0, "Computer Networks", "Medium",
     [("80", False), ("21", False), ("443", True), ("22", False)]),
    ("Which network device typically operates at the Data Link layer?", 2.0, "Computer Networks", "Medium",
     [("Hub", False), ("Switch", True), ("Router", False), ("Repeater", False)]),
    ("What is the primary function of DHCP on a network?", 1.0, "Computer Networks", "Easy",
     [("Encrypting network traffic", False), ("Automatically assigning IP addresses to devices", True),
      ("Translating domain names to IP addresses", False), ("Filtering malicious packets", False)]),
]  # total marks = 9

OOP_QUESTIONS = [
    ("What is encapsulation in object-oriented programming?", 1.0, "OOP", "Easy",
     [("Creating multiple objects from one class", False),
      ("Bundling data and the methods that operate on it within a single unit", True),
      ("Allowing a class to inherit from multiple parents", False),
      ("Converting an object into a string", False)]),
    ("A subclass providing its own specific implementation of a method already defined in its superclass is an example of what?", 2.0, "OOP", "Medium",
     [("Encapsulation", False), ("Method overriding (runtime polymorphism)", True),
      ("Method overloading", False), ("Abstraction", False)]),
    ("What is inheritance in object-oriented programming?", 1.0, "OOP", "Easy",
     [("A mechanism where a new class acquires properties and behavior from an existing class", True),
      ("A way to hide implementation details from the user", False),
      ("A technique for reducing memory usage", False),
      ("A rule requiring every class to have a constructor", False)]),
    ("What best describes an abstract class?", 2.0, "OOP", "Medium",
     [("A class that can never have any methods", False),
      ("A class that cannot be instantiated directly and may define abstract methods", True),
      ("A class used only for storing constants", False),
      ("A class that is automatically generated by the compiler", False)]),
    ("What is method overloading?", 2.0, "OOP", "Medium",
     [("Defining multiple methods with the same name but different parameter lists", True),
      ("Redefining a parent class method in a subclass", False),
      ("Calling a method recursively", False),
      ("Declaring a method as private", False)]),
    ("Which OOP principle allows a single interface to represent different underlying data types or classes?", 2.0, "OOP", "Hard",
     [("Encapsulation", False), ("Inheritance", False), ("Polymorphism", True), ("Composition", False)]),
]  # total marks = 10


# ---------------------------------------------------------------------
# Assessment definitions
# ---------------------------------------------------------------------

CANDIDATE_FACING_ASSESSMENTS = [
    {
        "name": "Python Programming Basics",
        "description": "Core Python syntax, data types, control flow, and fundamental language features.",
        "instructions": (
            "This assessment covers foundational Python programming concepts including data types, "
            "functions, exception handling, and common built-in operations. Read each question "
            "carefully — only one option is correct. You may navigate between questions freely and "
            "change your answers at any point before submitting."
        ),
        "duration_minutes": 30,
        "passing_marks": 12,
        "negative_marking_enabled": False,
        "negative_marking_value": 0.0,
        "monitoring_enabled": True,
        "questions": PYTHON_QUESTIONS,
    },
    {
        "name": "Artificial Intelligence Fundamentals",
        "description": "Core concepts in AI and machine learning, including supervised/unsupervised learning and neural networks.",
        "instructions": (
            "This assessment covers foundational artificial intelligence and machine learning "
            "concepts. Questions test conceptual understanding rather than mathematical derivation. "
            "Select the single best answer for each question."
        ),
        "duration_minutes": 20,
        "passing_marks": None,  # no explicit passing-marks given in the spec for this assessment;
        "negative_marking_enabled": False,                       # falls back to passing_score_percent (50%)
        "negative_marking_value": 0.0,
        "monitoring_enabled": True,
        "questions": AI_QUESTIONS,
    },
    {
        "name": "Aptitude Assessment",
        "description": "Quantitative reasoning, verbal reasoning, and logical/analytical thinking.",
        "instructions": (
            "This assessment covers quantitative aptitude, verbal reasoning, and logical puzzles. "
            "Some questions involve short calculations — a rough workspace (pen and paper) is "
            "permitted, but no calculators or external tools."
        ),
        "duration_minutes": 15,
        "passing_marks": None,  # no explicit passing-marks given; falls back to passing_score_percent (50%)
        "negative_marking_enabled": False,
        "negative_marking_value": 0.0,
        "monitoring_enabled": True,
        "questions": APTITUDE_QUESTIONS,
    },
]

# Inactive "question bank" containers — see module docstring for why
# these are modeled as inactive Assessments rather than a new table.
QUESTION_BANK_CONTAINERS = [
    ("Data Structures Question Bank", "Data Structures", DATA_STRUCTURES_QUESTIONS),
    ("DBMS Question Bank", "DBMS", DBMS_QUESTIONS),
    ("Operating Systems Question Bank", "Operating Systems", OS_QUESTIONS),
    ("Computer Networks Question Bank", "Computer Networks", NETWORKS_QUESTIONS),
    ("OOP Question Bank", "OOP", OOP_QUESTIONS),
]


def _create_assessment(name, description, instructions, duration_minutes, passing_marks,
                        negative_marking_enabled, negative_marking_value, monitoring_enabled,
                        is_active, questions):
    """Shared creation logic for both candidate-facing assessments and bank containers."""
    existing = Assessment.query.filter_by(name=name).first()
    if existing:
        print(f"Assessment '{name}' already exists (id={existing.id}) — skipping.")
        return existing

    assessment = Assessment(
        name=name,
        description=description,
        instructions=instructions,
        duration_minutes=duration_minutes,
        passing_marks=passing_marks,
        passing_score_percent=50,
        allowed_attempts=2,
        negative_marking_enabled=negative_marking_enabled,
        negative_marking_value=negative_marking_value,
        question_pattern="Multiple Choice (Single Answer)",
        monitoring_enabled=monitoring_enabled,
        is_active=is_active,
    )
    db.session.add(assessment)
    db.session.flush()  # assigns assessment.id without a full commit yet

    for order, (text, marks, category, difficulty, options) in enumerate(questions):
        question = Question(
            assessment_id=assessment.id, text=text, marks=marks, order=order,
            category=category, difficulty=difficulty,
        )
        db.session.add(question)
        db.session.flush()

        for opt_order, (opt_text, is_correct) in enumerate(options):
            db.session.add(Option(question_id=question.id, text=opt_text, is_correct=is_correct, order=opt_order))

    db.session.commit()
    print(f"Created assessment '{name}' (id={assessment.id}) with {len(questions)} questions, "
          f"active={is_active}.")
    return assessment


def seed_assessments():
    """Create the 3 candidate-facing assessments plus the 5 question-bank containers."""
    for spec in CANDIDATE_FACING_ASSESSMENTS:
        _create_assessment(
            name=spec["name"], description=spec["description"], instructions=spec["instructions"],
            duration_minutes=spec["duration_minutes"], passing_marks=spec["passing_marks"],
            negative_marking_enabled=spec["negative_marking_enabled"],
            negative_marking_value=spec["negative_marking_value"],
            monitoring_enabled=spec["monitoring_enabled"], is_active=True,
            questions=spec["questions"],
        )

    for name, category, questions in QUESTION_BANK_CONTAINERS:
        _create_assessment(
            name=name, description=f"Question bank — {category}.", instructions=None,
            duration_minutes=len(questions) * 2, passing_marks=None,
            negative_marking_enabled=False, negative_marking_value=0.0,
            monitoring_enabled=True, is_active=False,
            questions=questions,
        )

    total_questions = Question.query.count()
    print(f"Question bank now contains {total_questions} questions across "
          f"{db.session.query(Question.category).distinct().count()} categories.")


def seed_candidates(count: int):
    """Create `count` dummy candidate accounts via Faker, for UI/analytics testing."""
    from faker import Faker

    fake = Faker()
    created = 0

    for _ in range(count):
        email = fake.unique.email()
        if User.query.filter_by(email=email).first():
            continue

        user = User(
            full_name=fake.name(),
            email=email,
            integrity_score=random.choice([100, 100, 95, 90, 85, 70, 60, 45]),
        )
        user.set_password("password123")
        db.session.add(user)
        created += 1

    db.session.commit()
    print(f"Created {created} dummy candidate account(s) (password: 'password123' for all).")


def seed_invigilator():
    """Create one invigilator account (idempotent) for testing the invigilator dashboard."""
    email = "invigilator@proctoriq.test"
    existing = User.query.filter_by(email=email).first()
    if existing:
        print(f"Invigilator account already exists ({email}) — skipping.")
        return existing

    user = User(full_name="Alex Rivera", email=email, role="invigilator")
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()
    print(f"Created invigilator account: {email} / password123")
    return user


def seed_sample_sessions():
    """
    Create a few AssessmentSession rows (some in-progress, some
    completed with violations) for existing dummy candidates, so the
    invigilator dashboard, Analytics, and Violations pages have real
    data to show without requiring a live webcam test.
    """
    assessment = Assessment.query.filter_by(is_active=True).order_by(Assessment.id).first()
    if assessment is None:
        print("No active assessment found — run seed_assessments() first.")
        return

    candidates = User.query.filter_by(role="candidate").limit(4).all()
    if not candidates:
        print("No candidate accounts found to attach sample sessions to — skipping.")
        return

    from datetime import datetime, timedelta
    from models.assessment import AssessmentSession, AssessmentResult
    from services.event_logger import log_event, SEVERITY_WARNING, SEVERITY_CRITICAL, SEVERITY_INFO

    created = 0
    for i, candidate in enumerate(candidates):
        if i % 2 == 0:
            session = AssessmentSession(
                user_id=candidate.id,
                assessment_id=assessment.id,
                started_at=datetime.utcnow() - timedelta(minutes=5),
                ends_at=datetime.utcnow() + timedelta(minutes=assessment.duration_minutes - 5),
                status="in_progress",
                current_question_index=random.randint(0, assessment.total_questions - 1),
            )
            db.session.add(session)
            log_event(candidate.id, "monitoring_started", SEVERITY_INFO)
            log_event(candidate.id, "tab_switch", SEVERITY_WARNING)
            candidate.integrity_score = max(0, candidate.integrity_score - 5)
        else:
            session = AssessmentSession(
                user_id=candidate.id,
                assessment_id=assessment.id,
                started_at=datetime.utcnow() - timedelta(hours=2),
                ends_at=datetime.utcnow() - timedelta(hours=2) + timedelta(minutes=assessment.duration_minutes),
                submitted_at=datetime.utcnow() - timedelta(hours=1, minutes=40),
                status="submitted",
                integrity_score_at_submit=candidate.integrity_score,
            )
            db.session.add(session)
            db.session.flush()
            sample_score = round(assessment.total_marks * 0.7, 1)
            db.session.add(AssessmentResult(
                session_id=session.id, user_id=candidate.id, assessment_id=assessment.id,
                score=sample_score, total_marks=assessment.total_marks,
                percentage=round(sample_score / assessment.total_marks * 100, 2),
                passed=(assessment.passing_marks is None and sample_score / assessment.total_marks * 100 >= assessment.passing_score_percent)
                       or (assessment.passing_marks is not None and sample_score >= assessment.passing_marks),
                correct_count=max(1, assessment.total_questions - 3), incorrect_count=2, unanswered_count=1,
                submitted_at=session.submitted_at,
            ))
            log_event(candidate.id, "multiple_faces", SEVERITY_CRITICAL)
            log_event(candidate.id, "assessment_submitted", SEVERITY_INFO)

        created += 1

    db.session.commit()
    print(f"Created {created} sample assessment session(s) with monitoring events.")


def main():
    parser = argparse.ArgumentParser(description="Seed the database with sample assessment + test data.")
    parser.add_argument("--candidates", type=int, default=5, help="Number of dummy candidates to create (default: 5)")
    parser.add_argument("--no-candidates", action="store_true", help="Skip creating dummy candidates")
    parser.add_argument("--no-sessions", action="store_true", help="Skip creating sample assessment sessions")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        seed_assessments()
        seed_invigilator()
        if not args.no_candidates:
            seed_candidates(args.candidates)
        if not args.no_sessions:
            seed_sample_sessions()

    print("Seeding complete.")


if __name__ == "__main__":
    sys.exit(main())
