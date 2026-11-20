# IDAI102-2605556--Jaydeep-Desai.
ShopImpact -- Conscious Shopping Dashboard
 
 
Streamlit link of the app: https://idai102-2605556--jaydeep-desai-as8tttzxupl9th5orhy3la.streamlit.app


Shop smarter. Live greener.

ShopImpact is a Python-based web application concept that helps people
understand the estimated environmental impact of their shopping habits.
Users can record planned or completed purchases, view spending and
estimated CO₂-impact summaries, explore lower-impact alternatives, and
track sustainability-focused achievements.
Project status: Update this section as development progresses. Do
not describe a feature as complete until it has been implemented and
tested.

Table of Contents
- Project Overview
- Problem Statement
- Project Objectives
- Key Features
- Technology Stack
- How the Application Works
- Environmental Impact
  Calculation
- Python Concepts Demonstrated
- Project Structure
- Installation and Local Setup
- Run the Application
- Deployment on Streamlit Community
  Cloud
- Testing
- Limitations and Responsible Use
- Future Improvements
- Credits
Project Overview
ShopImpact is designed as a clean, accessible, and easy-to-use
sustainability dashboard. It turns shopping records into understandable
summaries so users can reflect on their purchasing patterns.

The application is intended for students, young adults, families, and
anyone interested in more conscious shopping. Its goal is to encourage
awareness and informed choices---not to make users feel guilty about
purchases.
Problem Statement
The environmental impact of everyday purchases is not always visible to
consumers. People may find it difficult to compare shopping habits,
understand which categories contribute most to their estimated
footprint, or identify practical alternatives.

ShopImpact addresses this awareness gap by allowing users to record
purchases and view an estimated impact summary alongside their spending
history.
Project Objectives
1. Build an interactive web application using Python and Streamlit.
2. Apply Python lists, dictionaries, functions, loops, and conditional
   statements to a practical problem.
3. Use date-based data handling to create monthly summaries.
4. Present purchase and impact information through clear dashboards and
   charts.
5. Suggest practical lower-impact shopping habits and alternatives.
6. Include creative Python Turtle graphics.
7. Test, document, and prepare the application for online deployment.
8. Consider accuracy, accessibility, privacy, and the social impact of
   the application.
Key Features
The following describes the intended application scope. Update the
status of each feature as it is implemented and tested.
  Feature                             Description
  Overview dashboard                  Summarises monthly spending,
estimated CO₂ impact, purchase
count, and qualifying lower-impact
choices.

  Add purchase                        Records product name, category,
brand, price, date, and whether the
purchase is planned or completed.

  Automatic impact estimate           Applies a configured category
multiplier to the purchase price.

  Impact analysis                     Displays category breakdowns and
trends using charts.

  Green alternatives                  Suggests practical lower-impact
product characteristics and
shopping habits by category.

  Achievements                        Awards badges when defined
conditions are met.

  Shopping history                    Supports searching, filtering,
reviewing, editing, and deleting
purchase records.

  Data export                         Allows purchase records to be
downloaded as a CSV file.

  Turtle graphics                     Uses Python Turtle to create
environmental illustrations such as
leaves, footprints, or badges.

  Demo data                           Provides sample records so users
can explore the dashboard.
Settings                            Provides available preferences such
as currency, targets, and theme.
Technology Stack
- Python -- application logic and calculations.
- Streamlit -- interactive web interface.
- Pandas -- tabular data handling and summaries.
- Datetime -- purchase dates and monthly filtering.
- Plotly / Streamlit charts -- data visualisation, depending on
  the implementation.
- Python Turtle -- generated environmental illustrations.
- GitHub -- source-code repository and version control.
- Streamlit Community Cloud -- intended hosting platform.
How the Application Works
1. The user opens the ShopImpact dashboard.
2. The user records a planned or completed purchase.
3. The application validates the entered information.
4. The application selects the configured multiplier for the chosen
   product category.
5. It calculates an estimated impact value.
6. The purchase is added to the application's records.
7. Dashboard cards, charts, history, and eligible achievements are
   recalculated from the records.
8. The user can review category insights and explore suggested
   alternatives.
Environmental Impact Calculation
The assignment brief specifies a simplified calculation:

Estimated impact = Purchase price × Category multiplier

The application stores category multipliers in a Python dictionary so
they can be maintained centrally.

The multiplier values must be documented with their units and source or
clearly labelled as illustrative assumptions. A price-based calculation
is a simplified educational estimate; it is not a direct measurement
of a product's actual carbon footprint or a full lifecycle assessment.

The application should display this limitation near the result so users
do not mistake an estimate for verified emissions data. Currency and
multiplier units must be handled consistently.
Python Concepts Demonstrated
  Python concept                      How it is used
  Variables and data types            Store product details, prices,
dates, and calculated values.

  Lists                               Maintain a collection of purchase
records.

  Dictionaries                        Represent individual purchases and
category multipliers.

  Conditional statements              Validate inputs, classify records,
and determine achievement
eligibility.

  Loops                               Process purchases and calculate
totals.

  Functions                           Separate calculations, validation,
summaries, and badge logic into
reusable units.

  Datetime                            Group records by month and filter
by date.

  Pandas                              Organise records and prepare data
for charts and exports.
Streamlit session state             Maintain application state during a
user session.
Project Structure
The repository may use the following modular structure. Adjust it to
match the actual files in the finished project.
ShopImpact/
├── app.py
├── requirements.txt
├── README.md
├── turtle_art.py
├── assets/
│   ├── logo.png
│   ├── leaf.png
│   ├── footprint.png
│   └── badges/
└── modules/
    ├── calculations.py
    ├── purchases.py
    ├── analytics.py
    ├── achievements.py
    └── recommendations.py
    Deployment on Streamlit Community Cloud
1. Push the completed project files to a GitHub repository.
2. Confirm that app.py, requirements.txt, and all required assets
   and modules are included.
3. Sign in to Streamlit Community Cloud.
4. Create a new app and connect the GitHub repository.
5. Select the correct branch and the main application file (app.py).
6. Deploy the application.
7. Open the deployed URL and test the main user journeys.
8. Add the verified live application URL below.
GitHub repository: ADD_GITHUB_REPOSITORY_URL

Live application: ADD_VERIFIED_STREAMLIT_APP_URL

Do not add a link until the repository or deployment actually exists and
has been checked.
Testing
Test the application with a range of sample purchases, including
different categories, prices, dates, and purchase statuses.

Suggested checks:
- Add a valid purchase.
- Reject missing or invalid input.
- Confirm the impact estimate uses the intended category multiplier.
- Edit and delete a purchase.
- Confirm dashboard totals update after each change.
- Check monthly and category filters.
- Check chart values against the underlying records.
- Verify achievement rules.
- Download and inspect the CSV export.
- Confirm Turtle-generated images display in the deployed interface.
- Check empty states and demo-data behaviour.
- Test the layout on desktop and mobile-sized screens.
- Confirm the deployed app starts without missing-package or
  missing-file errors.
Record the actual tests performed and their outcomes before final
submission.
Limitations and Responsible Use
- Estimates are not measurements: The simplified price-based
  formula cannot establish the actual emissions of an individual
  product.
- Multiplier quality matters: Results depend on the units,
  assumptions, and reliability of the configured multipliers.
- Brand claims require evidence: Do not label a brand ethical,
  certified, or sustainable without reliable supporting information.
- Data persistence: If the application uses Streamlit session
  state only, data may not be permanently stored across sessions or
  deployments. Explain the actual storage behaviour in the finished
  application.
- Not purchasing advice: Suggestions are general awareness
  information. Users should consider product quality, durability,
  accessibility, and their own needs.
- Privacy: Do not collect unnecessary personal information.
  Explain any data storage and export behaviour clearly.
Future Improvements
Possible future enhancements include:
- Persistent user accounts and secure database storage.
- More reliable product-level environmental datasets.
- Product lifecycle information where trustworthy data is available.
- Additional languages and accessibility improvements.
- More detailed comparison tools.
- Optional integrations with verified product databases.
These are future possibilities and should not be presented as existing
features unless implemented.
Credits
Created as an individual project for the Artificial Intelligence --
Python Programming CRS Summative Assessment.

Project: ShopImpact -- Conscious Shopping Dashboard
Student: ADD STUDENT NAME
School: ADD SCHOOL NAME
Course: Python Programming
CRS: Artificial Intelligence
Shop smarter. Live greener.
