import pandas as pd

class AcademicEarlyWarningSystem:
    def __init__(self,csv_file):
        self.csv_file=csv_file
        self.data=None

    def load_from_csv(self):
        self.data=pd.read_csv(self.csv_file)

        required_columns=["Student_ID" , "Final_Exam_Score"]

        for column in required_columns:
            if column not in self.data.columns:
                raise ValueError(f"Missing column: {column}")

        return self.data

    def predict_student_at_risk(self,pass_mark=50.0):
        if pass_mark <0:
            raise ValueError("pasmark cannot be negative\n")
        if self.data is None:
            raise RuntimeError("Load the CSV FILE")
        at_risk=self.data[
            self.data["Final_Exam_Score"] < pass_mark
		]
        return at_risk

    def summary_report(self):
        if self.data is None:
            raise RuntimeError("Load the CSV first")

        total_students=len(self.data)
        students_at_risk=self.predict_student_at_risk()

        at_risk_count=len(students_at_risk)
        passed_count=total_students - at_risk_count

        pass_percentage=((passed_count/total_students)*100 if total_students > 0 else 0)

        report={
			"Total_Students" : total_students,
            "Students_at_risk": students_at_risk,
            "Passed Students" :passed_count,
            "pass_percentage": round(pass_percentage,2)
		}
        return report
