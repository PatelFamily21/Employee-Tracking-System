### Employee Tracking System

**A comprehensive system for tracking employee attendance, work assignments, and administrative tasks.**  
This platform is designed to streamline employee management processes within an organization, providing tools for both admin and employees to handle their tasks effectively. The system allows for user login and registration, assignment of tasks, attendance management, notice publishing, and request handling.

> **Work in Progress:**  
This project is under active development. Some features may be incomplete or subject to changes. Contributions and feedback are welcome.

#### Key Features:
- **User Management:** Admin and employee roles with customized access.
- **Attendance Management:** Track employee attendance and manage working hours.
- **Work Assignments:** Admins assign tasks to employees; employees can update progress.
- **Request Handling:** Employees can send requests, and admins can manage them.
- **Notice Board:** Admins can publish important notices visible to all employees.

#### Technologies Used:
- **Frontend:** HTML, CSS, JavaScript
- **Backend:** Python (Django Framework)
- **Database:** MySQL
- **Authentication:** Custom user roles (Admin, Employee)

#### Installation:
1. Clone the repository:
   ```bash
   git clone https://github.com/PatelFamily21/Employee-Tracking-System/Employee-Tracking-System.git
   ```
2. Navigate to the project directory:
   ```bash
   cd employee-tracking-system
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set up the database and run migrations:
   ```bash
   python manage.py migrate
   ```
5. Start the development server:
   ```bash
   python manage.py runserver
   ```

#### How to Contribute:
- Fork the repository, create a branch, and make your changes.
- Submit a pull request with a clear description of the changes.

Feel free to explore and contribute to the development of the Employee Tracking System!
