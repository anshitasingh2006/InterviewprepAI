from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import json
import os
import speech_recognition as sr
from gtts import gTTS
from pydub import AudioSegment
from pydub.utils import which
import hashlib
import tempfile
import requests

# Load .env file manually if exists
env_path = '.env' if os.path.exists('.env') else ('../.env' if os.path.exists('../.env') else None)
if env_path:
    with open(env_path) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, val = line.strip().split('=', 1)
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

# Optional imports for PDF/DOCX
try:
    import pdfplumber
    has_pdfplumber = True
except ImportError:
    has_pdfplumber = False

try:
    from docx import Document
    has_docx = True
except ImportError:
    has_docx = False

app = Flask(__name__)
app.secret_key = 'your_secret_key_change_this_in_production'

# Set ffmpeg and ffprobe paths with error handling
try:
    ffmpeg_path = r"C:\ffmpeg\bin\ffmpeg.exe"
    ffprobe_path = r"C:\ffmpeg\bin\ffprobe.exe"

    # Check if files exist
    if os.path.exists(ffmpeg_path) and os.path.exists(ffprobe_path):
        AudioSegment.converter = ffmpeg_path
        AudioSegment.ffprobe = ffprobe_path
        os.environ["PATH"] += os.pathsep + os.path.dirname(ffmpeg_path)
        print("✅ ffmpeg configured successfully")
    else:
        print("⚠️ Warning: ffmpeg paths not found. Audio conversion may not work.")

    print("ffmpeg path:", which("ffmpeg"))
    print("ffprobe path:", which("ffprobe"))
except Exception as e:
    print(f"⚠️ Warning: Error setting up ffmpeg: {e}")

USER_FILE = 'users.json'

# Create static directory if it doesn't exist
os.makedirs('static', exist_ok=True)

# Role-based question sets
ROLE_QUESTIONS = {
    "frontend": [
        {
            "question": "What's the difference between let, const, and var?",
            "ideal": "Use `let` for block-scoped variables that can be reassigned, `const` for block-scoped constants that cannot be reassigned, and avoid `var` as it's function-scoped with hoisting behavior that can lead to unexpected results."
        },
        {
            "question": "What is the virtual DOM?",
            "ideal": "The virtual DOM is a JavaScript representation of the real DOM kept in memory. React uses it to optimize rendering by comparing the current virtual DOM with the previous version (diffing) and only updating the parts of the real DOM that have actually changed."
        },
        {
            "question": "How do you manage state in React?",
            "ideal": "State in React can be managed using useState hook for local component state, useReducer for complex state logic, Context API for global state, or external libraries like Redux/Zustand for application-wide state management."
        },
        {
            "question": "Explain the box model in CSS.",
            "ideal": "The CSS box model consists of content, padding, border, and margin layers. The total element size includes content + padding + border, while margin creates space between elements. Use box-sizing: border-box to include padding and border in the element's total width/height."
        },
        {
            "question": "What is event delegation and why is it useful?",
            "ideal": "Event delegation attaches a single event listener to a parent element to handle events for multiple child elements using event bubbling. It's useful for dynamic content, better performance with many elements, and automatic handling of newly added elements."
        }
    ],
    "uiux": [
        {
            "question": "What is the difference between UX and UI?",
            "ideal": "UX (User Experience) focuses on the overall user journey, research, wireframing, and problem-solving to create meaningful experiences. UI (User Interface) focuses on visual design, typography, colors, and interactive elements that users directly interact with."
        },
        {
            "question": "Explain the importance of user research in design.",
            "ideal": "User research validates design decisions with real data, identifies user pain points and needs, reduces development costs by catching issues early, ensures accessibility, and creates user-centered products that actually solve problems rather than assumptions."
        },
        {
            "question": "How do you handle user feedback?",
            "ideal": "Collect feedback through surveys, usability testing, and analytics. Categorize feedback by priority and impact, validate with data, communicate changes to stakeholders, implement iterative improvements, and follow up with users to measure success."
        }
    ],
    "backend": [
        {
            "question": "What is REST API?",
            "ideal": "REST (Representational State Transfer) is an architectural style for web services that uses standard HTTP methods (GET, POST, PUT, DELETE) and follows principles like statelessness, uniform interface, and cacheability. It typically uses JSON for data exchange and predictable URL patterns."
        },
        {
            "question": "How do you ensure secure user authentication?",
            "ideal": "Use strong password hashing (bcrypt, Argon2), implement JWT or OAuth 2.0, enforce HTTPS, add rate limiting, use MFA when possible, set secure session cookies, implement proper token expiration, and protect against common attacks like brute force and CSRF."
        },
        {
            "question": "What is the difference between SQL and NoSQL?",
            "ideal": "SQL databases use fixed schemas with ACID compliance and are best for complex relationships and transactions. NoSQL databases offer flexible schemas, horizontal scaling, and are better for big data and rapid development. Choose based on consistency vs availability needs."
        }
    ],
    "data-analyst": [
        {
            "question": "How do you handle missing data in datasets?",
            "ideal": "Handle missing data by first understanding why it's missing, then use strategies like deletion (if minimal), mean/median imputation for numerical data, mode imputation for categorical data, or advanced techniques like KNN imputation or predictive modeling based on data patterns."
        },
        {
            "question": "What is the difference between correlation and causation?",
            "ideal": "Correlation shows statistical relationship between variables but doesn't imply one causes the other. Causation means one variable directly influences another. Correlation can exist without causation due to confounding variables, reverse causation, or pure coincidence."
        },
        {
            "question": "Explain regression analysis.",
            "ideal": "Regression analysis predicts relationships between dependent and independent variables. Linear regression models straight-line relationships, while multiple regression uses several predictors. It helps predict outcomes, identify significant factors, and quantify relationships between variables."
        }
    ],
    "general": [
        {
            "question": "Tell me about yourself.",
            "ideal": "Provide a concise professional summary highlighting relevant experience, key skills, and career achievements. Focus on what makes you unique for the role, your passion for the field, and how your background aligns with the company's needs and values."
        },
        {
            "question": "What are your strengths and weaknesses?",
            "ideal": "For strengths, choose 2-3 relevant skills with specific examples. For weaknesses, mention a real area for improvement you're actively working on, show self-awareness, and explain the steps you're taking to address it."
        },
        {
            "question": "Where do you see yourself in 5 years?",
            "ideal": "Show ambition and growth mindset while aligning with the company's career paths. Mention skill development, leadership goals, and how you want to contribute to the organization's success. Avoid being too specific or mentioning other companies."
        }
    ],
    "software-developer": [
        {
            "question": "What are the key principles of Object-Oriented Programming?",
            "ideal": "The four main principles are: Encapsulation (bundling data and methods), Inheritance (deriving new classes from existing ones), Polymorphism (same interface for different implementations), and Abstraction (hiding complex implementation details while exposing simple interfaces)."
        },
        {
            "question": "Explain the difference between a process and a thread.",
            "ideal": "A process is an independent program execution with its own memory space, while a thread is a lightweight unit within a process that shares memory. Processes are isolated and communicate via IPC, threads share resources and communicate through shared memory."
        },
        {
            "question": "How do you handle memory management in your applications?",
            "ideal": "Use automatic garbage collection in managed languages, implement proper resource disposal patterns, avoid memory leaks by cleaning up event listeners and timers, use object pooling for frequently created objects, and profile memory usage to identify bottlenecks."
        },
        {
            "question": "Describe a time you debugged a tough issue in your code.",
            "ideal": "Describe the problem, your systematic debugging approach (logging, breakpoints, isolation), tools used, how you identified the root cause, the solution implemented, and lessons learned. Emphasize problem-solving methodology over just the technical fix."
        },
        {
            "question": "What design patterns have you used and why?",
            "ideal": "Mention specific patterns like Singleton for single instances, Observer for event handling, Factory for object creation, MVC for separation of concerns, or Strategy for algorithm selection. Explain the problem each pattern solved and why it was the right choice."
        }
    ],
    "data-scientist": [
        {
            "question": "What's the difference between supervised and unsupervised learning?",
            "ideal": "Supervised learning uses labeled training data to predict outcomes (classification/regression), like predicting house prices. Unsupervised learning finds patterns in unlabeled data through clustering, dimensionality reduction, or association rules without predefined target variables."
        },
        {
            "question": "How do you handle missing or corrupted data in a dataset?",
            "ideal": "First analyze missing data patterns, then use deletion if minimal, imputation (mean/median/mode) for systematic missingness, or advanced techniques like KNN imputation. For corrupted data, use outlier detection, data validation rules, and domain knowledge to clean or exclude problematic records."
        },
        {
            "question": "What is overfitting, and how can you prevent it?",
            "ideal": "Overfitting occurs when a model learns training data too well but performs poorly on new data. Prevent it using cross-validation, regularization (L1/L2), early stopping, dropout in neural networks, feature selection, and using more training data or simpler models."
        },
        {
            "question": "Explain a machine learning project you've worked on.",
            "ideal": "Describe the business problem, data sources and preprocessing steps, model selection and evaluation metrics, challenges faced, results achieved, and business impact. Focus on your decision-making process and how you validated the model's effectiveness."
        },
        {
            "question": "Which Python libraries do you frequently use for data analysis?",
            "ideal": "Pandas for data manipulation, NumPy for numerical computing, Matplotlib/Seaborn for visualization, Scikit-learn for machine learning, Jupyter for interactive development, and specialized libraries like TensorFlow/PyTorch for deep learning or Statsmodels for statistical analysis."
        }
    ],
    "cybersecurity": [
        {
            "question": "What are the most common types of cyber attacks?",
            "ideal": "Common attacks include phishing (social engineering), malware (viruses, ransomware), SQL injection, cross-site scripting (XSS), DDoS attacks, man-in-the-middle attacks, and insider threats. Each requires different prevention and detection strategies."
        },
        {
            "question": "Explain the concept of penetration testing.",
            "ideal": "Penetration testing is authorized simulated cyber attacks to identify security vulnerabilities. It involves reconnaissance, scanning, exploitation, and reporting phases. Pen testing helps organizations understand their security posture and prioritize remediation efforts."
        },
        {
            "question": "How do you secure a web application?",
            "ideal": "Implement input validation, use HTTPS, secure authentication (strong passwords, MFA), implement proper session management, protect against OWASP Top 10 vulnerabilities, regular security updates, security headers, and conduct regular security audits and penetration testing."
        },
        {
            "question": "What is the difference between symmetric and asymmetric encryption?",
            "ideal": "Symmetric encryption uses the same key for encryption and decryption (faster, good for bulk data). Asymmetric encryption uses key pairs (public/private) for encryption/decryption (slower, good for key exchange and digital signatures). Often used together in hybrid systems."
        },
        {
            "question": "How would you respond to a data breach?",
            "ideal": "Immediately contain the breach, assess the scope and impact, notify relevant stakeholders and authorities, preserve evidence for investigation, implement remediation measures, communicate with affected parties, and conduct post-incident review to prevent future breaches."
        }
    ],
    "web-developer": [
        {
            "question": "What is the difference between HTML, CSS, and JavaScript?",
            "ideal": "HTML provides structure and content (markup), CSS handles presentation and styling (colors, layout, fonts), and JavaScript adds interactivity and dynamic behavior (user interactions, API calls, DOM manipulation). They work together to create complete web experiences."
        },
        {
            "question": "How do you make a website responsive?",
            "ideal": "Use CSS media queries for different screen sizes, flexible grid systems (CSS Grid/Flexbox), relative units (%, em, rem), responsive images with srcset, mobile-first design approach, and test across multiple devices and screen sizes."
        },
        {
            "question": "What is the DOM and how do you manipulate it?",
            "ideal": "DOM (Document Object Model) is a programming interface representing HTML as a tree structure. Manipulate it using JavaScript methods like getElementById, querySelector, createElement, appendChild, and addEventListener to dynamically change content, styles, and behavior."
        },
        {
            "question": "Explain the difference between GET and POST requests.",
            "ideal": "GET requests retrieve data, are idempotent, cacheable, and pass parameters in the URL (visible and limited). POST requests send data to create/update resources, are not idempotent, not cacheable, and pass data in the request body (secure and unlimited)."
        },
        {
            "question": "How do you optimize website performance?",
            "ideal": "Optimize images (compression, WebP format), minify CSS/JS, use CDNs, implement caching strategies, reduce HTTP requests, lazy load content, optimize critical rendering path, compress assets with Gzip, and monitor performance with tools like Lighthouse."
        }
    ],
    "system-admin": [
        {
            "question": "What's the difference between Linux and Windows server environments?",
            "ideal": "Linux is open-source, command-line focused, highly customizable, better for web servers and development. Windows Server is proprietary, GUI-friendly, integrates well with Microsoft ecosystem, and is preferred for enterprise applications requiring Active Directory and .NET framework."
        },
        {
            "question": "How do you monitor and maintain system health?",
            "ideal": "Use monitoring tools (Nagios, Zabbix, Datadog), track key metrics (CPU, memory, disk, network), set up alerts for thresholds, perform regular maintenance (updates, backups), automate routine tasks, and maintain documentation of system configurations."
        },
        {
            "question": "What steps would you take to troubleshoot network issues?",
            "ideal": "Start with basic connectivity tests (ping, traceroute), check physical connections, verify IP configuration, examine DNS resolution, analyze network logs, use network monitoring tools, isolate the problem scope, and document findings for future reference."
        },
        {
            "question": "How do you handle system backups and disaster recovery?",
            "ideal": "Implement automated backup schedules, use 3-2-1 backup rule (3 copies, 2 different media, 1 offsite), regularly test backup restoration, document recovery procedures, maintain disaster recovery plans, and conduct periodic drills to ensure effectiveness."
        },
        {
            "question": "Explain how you manage user permissions and security policies.",
            "ideal": "Implement principle of least privilege, use role-based access control (RBAC), regular access reviews, strong password policies, multi-factor authentication, audit user activities, promptly remove access for terminated users, and maintain security compliance standards."
        }
    ],
    "product-manager": [
        {
            "question": "How do you prioritize features in a product roadmap?",
            "ideal": "Use frameworks like RICE (Reach, Impact, Confidence, Effort), MoSCoW method, or value vs effort matrix. Consider user feedback, business goals, technical constraints, market trends, and resource availability. Regularly review and adjust priorities based on new data."
        },
        {
            "question": "Describe your experience working with cross-functional teams.",
            "ideal": "Emphasize communication skills, stakeholder management, conflict resolution, and alignment of different team objectives. Provide examples of successful collaboration between engineering, design, marketing, and sales teams to deliver products on time and within scope."
        },
        {
            "question": "What tools do you use for project and product management?",
            "ideal": "Mention tools like Jira for agile project management, Confluence for documentation, Slack for communication, Figma for design collaboration, Google Analytics for user behavior, and product management platforms like ProductPlan or Roadmunk for roadmapping."
        },
        {
            "question": "How do you handle conflicting feedback from stakeholders?",
            "ideal": "Listen to all perspectives, identify underlying needs behind requests, use data and user research to support decisions, facilitate discussions to find common ground, communicate trade-offs clearly, and ensure decisions align with product strategy and business goals."
        },
        {
            "question": "Give an example of a product you launched and how you measured its success.",
            "ideal": "Describe the product, launch strategy, key metrics defined (user adoption, retention, revenue), measurement methods used, actual results achieved, lessons learned, and how you iterated based on post-launch data and user feedback."
        }
    ],
    "management-trainee": [
        {
            "question": "Why do you want to become a management trainee?",
            "ideal": "Express genuine interest in leadership development, desire to understand business operations across departments, eagerness to learn from experienced managers, and long-term career goals in management. Show enthusiasm for the company's training program and growth opportunities."
        },
        {
            "question": "How do you prioritize tasks under pressure?",
            "ideal": "Use prioritization frameworks (Eisenhower Matrix), assess urgency vs importance, communicate with stakeholders about timelines, break complex tasks into manageable steps, delegate when possible, and maintain calm under pressure while ensuring quality delivery."
        },
        {
            "question": "Explain a time when you took initiative in a project.",
            "ideal": "Describe a specific situation where you identified an opportunity or problem, took proactive steps without being asked, the actions you implemented, challenges faced, results achieved, and what you learned from the experience."
        },
        {
            "question": "What do you expect to learn during your training period?",
            "ideal": "Mention specific areas like leadership skills, business operations, industry knowledge, project management, team collaboration, strategic thinking, and how these align with your career goals and the company's objectives."
        },
        {
            "question": "How do you adapt to changes in a fast-paced environment?",
            "ideal": "Demonstrate flexibility, continuous learning mindset, ability to quickly assess new situations, effective communication during transitions, stress management techniques, and examples of successfully adapting to change in previous experiences."
        }
    ],
    "sales-executive": [
        {
            "question": "What strategies do you use to close a deal?",
            "ideal": "Build rapport and trust, understand customer needs thoroughly, present solutions that address specific pain points, handle objections professionally, create urgency when appropriate, use consultative selling approach, and follow up consistently until closure."
        },
        {
            "question": "How do you handle customer objections?",
            "ideal": "Listen actively to understand the real concern, acknowledge the objection, ask clarifying questions, provide relevant information or alternatives, use social proof or testimonials, and turn objections into opportunities to demonstrate value."
        },
        {
            "question": "Tell me about a successful sales pitch you delivered.",
            "ideal": "Describe the client situation, your preparation process, how you tailored the pitch to their needs, key points that resonated, how you handled questions or concerns, the outcome achieved, and lessons learned for future pitches."
        },
        {
            "question": "What CRM tools have you worked with?",
            "ideal": "Mention specific tools like Salesforce, HubSpot, or Pipedrive, explain how you used them for lead management, tracking customer interactions, forecasting sales, generating reports, and maintaining customer relationships throughout the sales cycle."
        },
        {
            "question": "How do you meet or exceed your sales targets?",
            "ideal": "Set clear daily and weekly activity goals, maintain a robust pipeline, qualify leads effectively, focus on high-value prospects, track metrics regularly, learn from successful and unsuccessful deals, and continuously improve sales techniques."
        }
    ],
    "marketing-manager": [
        {
            "question": "Describe a successful marketing campaign you managed.",
            "ideal": "Outline the campaign objectives, target audience, strategy developed, channels used, budget allocation, execution timeline, metrics tracked, results achieved, and key learnings that influenced future campaigns."
        },
        {
            "question": "How do you track ROI on marketing activities?",
            "ideal": "Use analytics tools (Google Analytics, marketing automation platforms), track conversion funnels, calculate customer acquisition cost (CAC), measure lifetime value (LTV), attribute revenue to specific campaigns, and create regular performance reports with actionable insights."
        },
        {
            "question": "What are the latest digital marketing trends?",
            "ideal": "Mention current trends like AI-powered personalization, video marketing, influencer partnerships, voice search optimization, interactive content, privacy-first marketing, omnichannel experiences, and demonstrate awareness of how these impact marketing strategies."
        },
        {
            "question": "How do you handle tight deadlines with multiple campaigns?",
            "ideal": "Use project management tools, prioritize based on impact and deadlines, delegate tasks effectively, maintain clear communication with team members, build in buffer time for revisions, and establish efficient approval processes."
        },
        {
            "question": "What's your experience with SEO or SEM?",
            "ideal": "Describe specific SEO techniques used (keyword research, on-page optimization, link building), SEM campaign management (Google Ads, bid strategies, ad copy testing), tools utilized, results achieved, and how you stay updated with algorithm changes."
        }
    ],
    "business-analyst": [
        {
            "question": "What tools do you use for business analysis?",
            "ideal": "Mention tools like Microsoft Visio for process mapping, JIRA for requirements management, SQL for data analysis, Excel for data modeling, Tableau for visualization, and collaboration tools like Confluence for documentation."
        },
        {
            "question": "How do you gather requirements from stakeholders?",
            "ideal": "Conduct structured interviews, facilitate workshops, use surveys for broad input, observe current processes, analyze existing documentation, create user stories, validate requirements through prototypes, and ensure all stakeholder needs are captured and prioritized."
        },
        {
            "question": "What is a use case and how do you document it?",
            "ideal": "A use case describes how users interact with a system to achieve specific goals. Document with actors, preconditions, main flow, alternative flows, postconditions, and exceptions. Use clear, concise language and validate with stakeholders."
        },
        {
            "question": "Explain a business process improvement you implemented.",
            "ideal": "Describe the current state problems, analysis conducted, stakeholders involved, solution designed, implementation challenges, change management approach, measurable improvements achieved, and lessons learned for future projects."
        },
        {
            "question": "What's the difference between functional and non-functional requirements?",
            "ideal": "Functional requirements define what the system should do (features, capabilities, behaviors). Non-functional requirements define how the system should perform (performance, security, usability, reliability, scalability). Both are essential for successful system development."
        }
    ],
    "consultant": [
        {
            "question": "What is your consulting approach with a new client?",
            "ideal": "Start with thorough discovery to understand business context, stakeholders, and objectives. Conduct current state analysis, identify gaps and opportunities, develop tailored solutions, create implementation roadmap, and establish clear success metrics and communication protocols."
        },
        {
            "question": "How do you handle pushback from stakeholders?",
            "ideal": "Listen to understand underlying concerns, acknowledge valid points, provide data-driven rationale for recommendations, offer alternative approaches when possible, involve stakeholders in solution development, and maintain professional relationships while staying focused on objectives."
        },
        {
            "question": "Describe a situation where you delivered value under pressure.",
            "ideal": "Outline the challenging situation, time constraints faced, approach taken to prioritize deliverables, resources leveraged, communication strategy with stakeholders, specific value delivered, and how you maintained quality despite pressure."
        },
        {
            "question": "How do you keep your industry knowledge up to date?",
            "ideal": "Read industry publications, attend conferences and webinars, participate in professional networks, pursue relevant certifications, engage with thought leaders on social media, and apply learnings to current client work to test effectiveness."
        },
        {
            "question": "How do you define success in a consulting engagement?",
            "ideal": "Success is defined by achieving client objectives, delivering measurable business value, building client capability, meeting timeline and budget constraints, maintaining strong relationships, and creating sustainable solutions that continue to benefit the client long-term."
        }
    ],
    "hr": [
        {
            "question": "Walk me through your recruitment process.",
            "ideal": "Start with job analysis and requirement gathering, create compelling job descriptions, source candidates through multiple channels, screen resumes and conduct phone interviews, facilitate in-person/video interviews, check references, make offers, and ensure smooth onboarding."
        },
        {
            "question": "How do you handle conflict between employees?",
            "ideal": "Address conflicts early through direct communication, listen to all parties objectively, identify root causes, facilitate discussions to find common ground, document incidents and resolutions, provide mediation when needed, and follow up to ensure lasting resolution."
        },
        {
            "question": "What HR tools or platforms have you used?",
            "ideal": "Mention specific HRIS systems (Workday, BambooHR, SAP SuccessFactors), applicant tracking systems (Greenhouse, Lever), performance management tools (15Five, Lattice), and explain how you used them to streamline HR processes and improve employee experience."
        },
        {
            "question": "How do you ensure employee engagement?",
            "ideal": "Conduct regular engagement surveys, implement feedback mechanisms, recognize and reward achievements, provide career development opportunities, foster open communication, create inclusive culture, offer flexible work arrangements, and address concerns promptly."
        },
        {
            "question": "Tell me about a time you had to manage a difficult termination.",
            "ideal": "Describe the situation requiring termination, documentation gathered, consultation with legal/management, preparation of termination meeting, compassionate delivery of decision, handling of logistics (access, benefits, transition), and lessons learned for future situations."
        }
    ]
}


# Helper to extract text from PDF or DOCX file
def extract_resume_text(file):
    if not file or file.filename == '':
        return ""
    
    filename = file.filename.lower()
    suffix = os.path.splitext(filename)[1]
    
    if suffix not in ['.pdf', '.docx']:
        return ""
    
    # Save to a temporary file
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, file.filename)
    
    try:
        file.save(temp_path)
        
        if suffix == '.pdf':
            if not has_pdfplumber:
                print("⚠️ Warning: pdfplumber is not installed. Cannot parse PDF.")
                return "[PDF contents - parser not installed]"
            with pdfplumber.open(temp_path) as pdf:
                return "\n".join(page.extract_text() or "" for page in pdf.pages)
        elif suffix == '.docx':
            if not has_docx:
                print("⚠️ Warning: python-docx is not installed. Cannot parse DOCX.")
                return "[DOCX contents - parser not installed]"
            doc = Document(temp_path)
            return "\n".join(p.text for p in doc.paragraphs)
            
        return ""
    except Exception as e:
        print(f"Error extracting text from {filename}: {e}")
        return ""
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as cleanup_error:
                print(f"Warning: Could not clean up temp file {temp_path}: {cleanup_error}")


# Helper to generate custom questions using Gemini API
def generate_questions_with_gemini(job_description, resume_text, fallback_role):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("⚠️ GEMINI_API_KEY is not set. Falling back to keyword heuristic.")
        return None
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    prompt = (
        "You are an expert technical recruiter and interviewer. "
        "Generate a set of exactly 5 tailored interview questions with their corresponding ideal answers "
        "based on the job description and/or the candidate's resume provided below. "
        "Ensure the questions test relevant technical skills, experience, or situational scenario competence.\n\n"
        f"Job Description:\n{job_description or 'Not provided'}\n\n"
        f"Candidate Resume:\n{resume_text or 'Not provided'}\n\n"
        f"Fallback Role: {fallback_role}\n\n"
        "You MUST respond ONLY with a valid JSON array of objects. Do not include any markdown formatting (like ```json), "
        "conversational text, or notes. The JSON must exactly match the following schema:\n"
        "[\n"
        "  {\n"
        "    \"question\": \"String containing the interview question?\",\n"
        "    \"ideal\": \"String describing the ideal answer or key points the interviewer expects.\"\n"
        "  }\n"
        "]"
    )
    
    payload = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
        response.raise_for_status()
        result = response.json()
        
        candidates = result.get("candidates", [])
        if candidates:
            content_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
            # Clean possible markdown block if Gemini ignored the instruction
            if content_text.startswith("```"):
                lines = content_text.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].startswith("```"):
                    lines = lines[:-1]
                content_text = "\n".join(lines).strip()
            
            questions = json.loads(content_text)
            if isinstance(questions, list) and len(questions) > 0:
                validated = []
                for q in questions:
                    if isinstance(q, dict) and "question" in q:
                        validated.append({
                            "question": q["question"],
                            "ideal": q.get("ideal", "No ideal answer provided.")
                        })
                if len(validated) > 0:
                    return validated
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
    
    return None

# Keyword fallback matching if Gemini API is missing or fails
def fallback_question_generator(job_description, resume_text, selected_role):
    # Combine job description and resume to look for keywords
    text = (job_description + " " + resume_text).lower()
    
    # Map keywords to roles
    keywords_to_roles = {
        "frontend": ["react", "vue", "angular", "css", "html", "javascript", "js", "frontend", "front-end", "web design"],
        "backend": ["node", "express", "django", "flask", "springboot", "java", "sql", "database", "mongodb", "postgresql", "backend", "back-end", "api", "rest api"],
        "data-analyst": ["tableau", "powerbi", "excel", "data analyst", "visualization", "pandas"],
        "uiux": ["figma", "wireframe", "ui/ux", "ui-ux", "user experience", "user interface", "design thinking"],
        "data-scientist": ["machine learning", "ml", "data scientist", "pytorch", "tensorflow", "scikit-learn", "regression"],
        "cybersecurity": ["threat", "encryption", "penetration", "cybersecurity", "security audit", "firewall"],
        "web-developer": ["web developer", "website", "html/css"],
        "system-admin": ["linux", "server", "active directory", "zabbix", "nagios", "network admin", "system admin"],
        "product-manager": ["product manager", "roadmap", "feature priority"],
        "management-trainee": ["management trainee", "trainee", "operations"],
        "sales-executive": ["sales executive", "crm", "sales target", "sales pitch"],
        "marketing-manager": ["marketing", "campaign", "seo", "sem", "branding"],
        "business-analyst": ["business analyst", "use case", "kpi", "requirements gather"],
        "consultant": ["consulting", "consultant", "delivery", "client objective"],
        "hr": ["recruitment", "onboarding", "employee care", "hr", "human resources"]
    }
    
    # Count matches
    scores = {role: 0 for role in keywords_to_roles}
    for role, keywords in keywords_to_roles.items():
        for kw in keywords:
            scores[role] += text.count(kw)
            
    # Find role with maximum score (only if score > 0)
    best_role = selected_role
    best_score = 0
    for role, score in scores.items():
        if score > best_score:
            best_score = score
            best_role = role
            
    print(f"Fallback heuristic selected role: {best_role} (score: {best_score})")
    return best_role, ROLE_QUESTIONS.get(best_role, ROLE_QUESTIONS['general'])


# Load users from JSON
def load_users():
    try:
        if not os.path.exists(USER_FILE):
            return []
        with open(USER_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error loading users: {e}")
        return []


# Save new user to JSON
def save_user(email, password):
    try:
        users = load_users()
        users.append({'email': email, 'password': password})
        with open(USER_FILE, 'w') as f:
            json.dump(users, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving user: {e}")
        return False


@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        if not email or not password:
            flash("❌ Please enter both email and password.")
            return render_template('login.html')

        users = load_users()
        for user in users:
            if user['email'] == email and user['password'] == password:
                session['user'] = email
                return redirect(url_for('dashboard'))
        flash("❌ Invalid email or password. Please register if you don't have an account.")
        return render_template('login.html')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        if not email or not password:
            flash("❌ Please enter both email and password.")
            return render_template('register.html')

        users = load_users()
        for user in users:
            if user['email'] == email:
                flash("⚠️ User already exists. Please login.")
                return redirect(url_for('login'))

        if save_user(email, password):
            session['user'] = email
            flash("✅ Registration successful!")
            return redirect(url_for('dashboard'))
        else:
            flash("❌ Registration failed. Please try again.")
            return render_template('register.html')
    return render_template('register.html')


@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        flash("Please login to access dashboard.")
        return redirect(url_for('login'))
    return render_template('dashboard.html', user=session['user'])


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()  # ✅ clears the session (user, role, answers, etc.)
    return redirect(url_for('login'))  # Replace 'login' with your login route name



@app.route('/reset_interview')
def reset_interview():
    # Clear interview-specific session data
    interview_keys = ['current_role', 'current_question_index', 'answers', 'done']
    for key in interview_keys:
        session.pop(key, None)
    print("🔄 Interview session reset")
    return '', 204


@app.route('/start_fresh')
def start_fresh():
    # Force reset everything and redirect to dashboard
    interview_keys = ['current_role', 'current_question_index', 'answers', 'done']
    for key in interview_keys:
        session.pop(key, None)
    flash("✅ Interview reset successfully!")
    return redirect(url_for('dashboard'))


# NEW ROUTE: Set interview role
@app.route('/set_role', methods=['POST'])
def set_role():
    if 'user' not in session:
        return jsonify({"error": "Please login first"}), 401

    # Check if request is multipart/form-data
    if request.content_type and 'multipart/form-data' in request.content_type:
        role = request.form.get('role', 'general')
        job_description = request.form.get('jobDescription', '').strip()
        resume_file = request.files.get('resume')
    else:
        # Fallback to JSON
        data = request.get_json() or {}
        role = data.get('role', 'general')
        job_description = data.get('jobDescription', '').strip()
        resume_file = None

    # Validate fallback role
    if role not in ROLE_QUESTIONS:
        role = 'general'

    resume_text = ""
    if resume_file:
        resume_text = extract_resume_text(resume_file)

    # Initialize questions
    questions = None
    ai_reply_prefix = ""

    # Check if we have any input to customize the interview
    if job_description or resume_text:
        # 1. Try Gemini API
        gemini_questions = generate_questions_with_gemini(job_description, resume_text, role)
        if gemini_questions:
            questions = gemini_questions
            ai_reply_prefix = "Great! I've generated a customized mock interview based on your job description and resume. Let's begin!"
            print(f"🎯 Dynamic questions generated using Gemini API.")
        else:
            # 2. Heuristic fallback
            matched_role, matched_questions = fallback_question_generator(job_description, resume_text, role)
            questions = matched_questions
            if os.environ.get("GEMINI_API_KEY"):
                print(f"⚠️ Warning: Gemini generation failed. Matching keywords to the '{matched_role}' role.")
            else:
                print(f"⚠️ Warning: GEMINI_API_KEY not configured. Matching keywords to the '{matched_role}' role.")
            ai_reply_prefix = f"Great! Let's begin your {matched_role} mock interview."
            role = matched_role
    else:
        # No job description or resume provided, use standard role
        questions = ROLE_QUESTIONS[role]
        ai_reply_prefix = f"Great! Let's begin your {role} mock interview."

    # Initialize interview session
    session['current_role'] = role
    session['current_question_index'] = 0
    session['questions'] = questions
    session['answers'] = [{
        "question": "Preferred Interview Role",
        "answer": role
    }]
    session['done'] = False

    first_q = questions[0]
    if isinstance(first_q, dict):
        question_text = first_q.get("question", "Let's get started.")
    else:
        question_text = first_q

    ai_reply = f"{ai_reply_prefix} First question: {question_text}"

    print(f"🎯 Role set to: {role}")
    print(f"🎯 First question: {question_text}")

    return jsonify({
        "success": True,
        "role": role,
        "first_question": question_text,
        "ai_reply": ai_reply,
        "total_questions": len(questions)
    })


# Route to upload resume and extract text (returns it and stores it in session)
@app.route('/upload-resume', methods=['POST'])
def upload_resume():
    if 'user' not in session:
        return jsonify({"error": "Please login first"}), 401
        
    if 'resume' not in request.files:
        return jsonify({"error": "No resume file provided"}), 400
        
    file = request.files['resume']
    if file.filename == '':
        return jsonify({"error": "No resume file selected"}), 400
        
    try:
        text = extract_resume_text(file)
        session['extracted_resume_text'] = text
        return jsonify({
            "success": True,
            "text": text
        })
    except Exception as e:
        print(f"Error parsing resume: {e}")
        return jsonify({"error": f"Failed to parse resume: {str(e)}"}), 500



@app.route('/summary')
def summary():
    if 'user' not in session:
        return redirect(url_for('login'))
    answers = session.get('answers', [])
    return render_template("summary.html", answers=answers)


@app.route('/process_audio', methods=['POST'])
def process_audio():
    if 'user' not in session:
        return jsonify({"error": "Please login first"}), 401

    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    uploaded_audio = request.files['audio']
    if uploaded_audio.filename == '':
        return jsonify({"error": "No audio file selected"}), 400

    input_path = "static/temp_input.webm"
    output_path = "static/converted.wav"

    try:
        uploaded_audio.save(input_path)

        # Convert audio
        audio = AudioSegment.from_file(input_path)
        audio.export(output_path, format="wav")

        # Speech recognition with better settings
        recognizer = sr.Recognizer()

        # Adjust recognizer settings for better performance
        recognizer.energy_threshold = 4000  # Minimum audio energy to consider for recording
        recognizer.dynamic_energy_threshold = True
        recognizer.pause_threshold = 1.5  # Seconds of non-speaking audio before phrase is complete
        recognizer.phrase_threshold = 0.3  # Minimum seconds of speaking audio before we consider the speaking audio a phrase
        recognizer.non_speaking_duration = 1.5  # Seconds of non-speaking audio to keep on both sides

        with sr.AudioFile(output_path) as source:
            # Adjust for ambient noise
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            # Record the entire audio file
            audio_data = recognizer.record(source)

            # Use Google Speech Recognition with longer timeout
            transcript = recognizer.recognize_google(
                audio_data,
                language='en-US',
                show_all=False
            )

        print("📝 User said:", transcript)

        # Check if interview has been initialized
        if 'current_role' not in session or 'current_question_index' not in session:
            return jsonify({"error": "Interview not initialized. Please select a role first."})

        # Handle ongoing interview
        role = session['current_role']
        current_index = session['current_question_index']
        questions = session.get('questions', ROLE_QUESTIONS.get(role, ROLE_QUESTIONS['general']))

        print(f"🎯 Current role: {role}")
        print(f"🎯 Current question index: {current_index}")
        print(f"🎯 Total questions for {role}: {len(questions)}")

        # Validate current question index and reset if invalid
        if current_index < 0 or current_index >= len(questions):
            print(f"⚠️ Invalid question index {current_index} for role {role}. Resetting interview.")
            session['current_question_index'] = 0
            session['answers'] = [{
                "question": "Preferred Interview Role",
                "answer": role
            }]
            session['done'] = False
            first_q = questions[0]
            if isinstance(first_q, dict):
                q_text = first_q.get("question", "Let's get started.")
            else:
                q_text = first_q
            ai_reply = f"Let's restart your {role} interview. First question: {q_text}"
        else:
            question_data = questions[current_index]

            # Support for new format with ideal answers
            if isinstance(question_data, dict):
                q_text = question_data.get('question')
                ideal = question_data.get('ideal', 'No ideal answer provided.')
            else:
                q_text = question_data
                ideal = "No ideal answer provided."

            session['answers'].append({
                "question": q_text,
                "answer": transcript,
                "ideal": ideal
            })

            # Move to next question or finish
            next_index = current_index + 1
            if next_index < len(questions):
                next_question_data = questions[next_index]
                if isinstance(next_question_data, dict):
                    ai_reply = next_question_data.get('question', 'Next question not found.')
                else:
                    ai_reply = next_question_data

                session['current_question_index'] = next_index
                session['done'] = False
                print(f"🎯 Moving to question {next_index}: {ai_reply}")
            else:
                ai_reply = "Thank you! Your mock interview is complete. You can view your summary now."
                session['done'] = True
                print("🎯 Interview completed")

        # Generate audio response
        tts = gTTS(text=ai_reply, lang='en', slow=False)
        audio_path = "static/ai_reply.mp3"
        tts.save(audio_path)

        # Clean up temporary files
        try:
            if os.path.exists(input_path):
                os.remove(input_path)
            if os.path.exists(output_path):
                os.remove(output_path)
        except Exception as cleanup_error:
            print(f"Warning: Could not clean up temp files: {cleanup_error}")

        return jsonify({
            "transcript": transcript,
            "ai_reply": ai_reply,
            "audio_url": f"/static/ai_reply.mp3?v={hashlib.md5(ai_reply.encode()).hexdigest()[:8]}",
            "done": session.get('done', False)
        })

    except sr.UnknownValueError:
        return jsonify({"error": "Sorry, I couldn't understand your audio. Please try speaking more clearly."})
    except sr.RequestError as e:
        return jsonify({"error": f"Could not request results from speech recognition service: {e}"})
    except Exception as e:
        print(f"❌ Processing error: {e}")
        return jsonify({"error": "An error occurred while processing your audio. Please try again."})


@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500


if __name__ == '__main__':
    app.run(debug=True, port=5001)