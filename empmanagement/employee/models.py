from django.db import models

designations_opt = (
    ('Team Leader', 'Team Leader'),
    ('Project Manager', 'Project Manager'),
    ('Senior Developer', 'Senior Developer'),
    ('Junior Developer', 'Junior Developer'),
    ('Intern', 'Intern'),
    ('QA Tester', 'QA Tester')
)

months = (
    ('January', 'January'), ('February', 'February'), ('March', 'March'),
    ('April', 'April'), ('May', 'May'), ('June', 'June'),
    ('July', 'July'), ('August', 'August'), ('September', 'September'),
    ('October', 'October'), ('November', 'November'), ('December', 'December')
)

days = tuple((str(i), str(i)) for i in range(32))

# New Department Model
class Department(models.Model):
    dept_id = models.CharField(max_length=10, primary_key=True)  # e.g., "HR", "ENG", "SALES"
    name = models.CharField(max_length=50, unique=True)  # e.g., "Human Resources"
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class Employee(models.Model):
    eID = models.CharField(primary_key=True, max_length=20)
    firstName = models.CharField(max_length=50)
    middleName = models.CharField(max_length=50)
    lastName = models.CharField(max_length=50)
    phoneNo = models.CharField(max_length=12, unique=True)
    email = models.EmailField(max_length=70, unique=True)
    addharNo = models.CharField(max_length=20, unique=True)
    dOB = models.DateField()
    designation = models.CharField(max_length=50, choices=designations_opt)
    salary = models.CharField(max_length=20)
    joinDate = models.DateField()
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, related_name="employees")

    def __str__(self):
        return "%s %s" % (self.eID, self.firstName)

class Attendance(models.Model):
    eId = models.ForeignKey(Employee, on_delete=models.CASCADE)
    month = models.CharField(max_length=50, choices=months)
    days = models.PositiveSmallIntegerField()

    def __str__(self):
        return "%s %s" % (self.eId, self.month)

class Notice(models.Model):
    Id = models.CharField(primary_key=True, max_length=20)
    title = models.CharField(max_length=250)
    description = models.TextField()
    publishDate = models.DateTimeField()
    # Optional: Add department targeting
    departments = models.ManyToManyField(Department, blank=True, related_name="notices")

    def __str__(self):
        return self.title

class WorkAssignments(models.Model):  # Renamed to follow PEP 8
    Id = models.CharField(primary_key=True, max_length=20)
    assignerId = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="assignerId")
    work = models.TextField()
    assignDate = models.DateTimeField()
    dueDate = models.DateTimeField()
    taskerId = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="taskerId")

    def __str__(self):
        return f"WorkAssignment {self.Id}"

class Requests(models.Model):
    Id = models.CharField(primary_key=True, max_length=20)
    requesterId = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="requesterId")
    requestMessage = models.TextField()
    requestDate = models.DateTimeField()
    destinationEmployeeId = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="toEmployeeId")

    def __str__(self):
        return f"Request {self.Id}"