import camelot
import matplotlib.pyplot as plt
from pymongo import MongoClient
import math
from camelot.handlers import PDFHandler
import os


# Helper methods for _bbox
def top_mid(bbox):
    return ((bbox[0] + bbox[2]) / 2, bbox[3])


def bottom_mid(bbox):
    return ((bbox[0] + bbox[2]) / 2, bbox[1])


def distance(p1, p2):
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def get_closest_text(table, htext_objs):
    min_distance = 999  # Cause 9's are big :)
    best_guess = None
    table_mid = top_mid(table._bbox)  # Middle of the TOP of the table
    for obj in htext_objs:
        text_mid = bottom_mid(obj.bbox)  # Middle of the BOTTOM of the text
        d = distance(text_mid, table_mid)
        if d < min_distance:
            best_guess = obj.get_text().strip()
            min_distance = d
    return best_guess


def get_tables_and_titles(pdf_filename):
    """Here's my hacky code for grabbing tables and guessing at their titles"""
    my_handler = PDFHandler(pdf_filename)  # from camelot.handlers import PDFHandler
    tables = camelot.read_pdf(pdf_filename, pages="all")
    print("Extracting {:d} tables...".format(tables.n))
    titles = []
    with camelot.utils.TemporaryDirectory() as tempdir:
        for table in tables:
            my_handler._save_page(pdf_filename, table.page, tempdir)
            tmp_file_path = os.path.join(tempdir, f"page-{table.page}.pdf")
            layout, dim = camelot.utils.get_page_layout(tmp_file_path)
            htext_objs = camelot.utils.get_text_objects(layout, ltype="horizontal_text")
            titles.append(get_closest_text(table, htext_objs))  # Might be None

    tables = [table.df for table in tables]
    return titles, tables


def get_day_from_index(index, days_column):
    return days_column.iloc[index + 1]


# Extracting properties from a string
def extract_properties(s):
    if s.strip() == "":
        return None, None, None
    parts = s.split("\n")
    instructor_name = parts[-1] if len(parts) > 2 else None
    location = parts[-2] if len(parts) > 2 else parts[-1] if len(parts) > 1 else None
    course_name = (
        " ".join(parts[:-2])
        if len(parts) > 2
        else " ".join(parts[:-1])
        if len(parts) > 1
        else parts[0]
    )
    return course_name, location, instructor_name


# Extracting data from the pdf file
filename = "timetable_pdf/Main_Timetable.pdf"
[titles, tables] = get_tables_and_titles(filename)

# Fixing the days column empty cells
current_label = ""
for table in tables:
    days_column = table.iloc[:, 0]
    for index, value in days_column.items():
        if value.strip() != "":
            current_label = value
        else:
            table.iloc[index, 0] = current_label


# filter the columns
tables = [
    table.iloc[:, [i for i in range(10) if i % 2 != 0 or i == 0]] for table in tables
]


# MongoDB conection
client = MongoClient("localhost", 27017)
db = client["test-dev"]
collection = db["timetable"]
print(db.name)
print(collection.name)

# exttracting data from tables

for index in range(len(tables)):
    class_name = titles[index]
    data = {"class": class_name.strip(), "courses": []}

    # for row in tables[index]:
    table = tables[index]
    days_column = table.iloc[:, 0]
    table = table.drop(table.columns[0], axis=1)
    num_columns = table.shape[1]
    for i in range(num_columns):
        rows = table.iloc[:, i].tolist()
        time = "-".join([x for i, x in enumerate(rows[0].split("\n")) if i != 0])
        # print(rows)
        for index, item in enumerate(rows[1:]):
            if len(item.strip()) > 0:
                course_name, location, instructor_name = extract_properties(item)
                data["courses"].append(
                    {
                        "course": course_name,
                        "time": time,
                        "day": get_day_from_index(index, days_column),
                        "room": location,
                        "teacher": instructor_name,
                    }
                )
                # print(
                #    f"Time: {time}, Day: {get_day_from_index(index, days_column)}, Course Name: {course_name}, Location: {location}, Instructor: {instructor_name}"
                # )

    # Inserting data into the database
    print(f"Inserting data for {class_name}...")
    result = collection.insert_one(data)
    print(f"Data inserted with id: {result.inserted_id}")


"""
# MongoDB Collection Schema
timetable = [
    {
        "class": "BS-VIII(CS)-A",
        "courses": [
            {
                "course": "Discrete Mathematics",
                "time": "10:00 - 11:00",
                "day": "Monday",
                "room": "AB2, R#205",
                "teacher": "Dr. S. A. Khan",
            },
            {
                "course": "Data Structures",
                "time": "11:00 - 12:00",
                "day": "Tuesday",
                "room": "AB3, R#301",
                "teacher": "Prof. M. Ali",
            },
            # Add more courses as needed
        ],
    },
    # Add more classes as needed
]
"""
