from datetime import datetime, date, time
from decimal import Decimal
from enum import Enum
from typing import List, Optional
from dataclasses import dataclass


class DayStatus(Enum):
    """Work day status"""
    NORMAL = "normal"
    SHORT = "short"
    ABSENT = "absent"
    OVERTIME = "overtime"


class DayType(Enum):
    """Day type by calendar"""
    WORKDAY = "workday"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"


@dataclass
class TimeStamp:
    """Fingerprint sensor timestamp record"""
    employee_id: str
    timestamp: datetime
    
    def __post_init__(self):
        if not self.employee_id:
            raise ValueError("Employee ID cannot be empty")
        if not isinstance(self.timestamp, datetime):
            raise ValueError("Timestamp must be a datetime object")


@dataclass
class WorkDay:
    """Single employee work day"""
    date: date
    employee_id: str
    timestamps: List[TimeStamp]
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    worked_seconds: int = 0
    status: DayStatus = DayStatus.NORMAL
    day_type: DayType = DayType.WORKDAY
    
    def __post_init__(self):
        if not self.employee_id:
            raise ValueError("Employee ID cannot be empty")
        if not isinstance(self.date, date):
            raise ValueError("Date must be a date object")
        if self.worked_seconds < 0:
            raise ValueError("Worked seconds cannot be negative")
    
    @property
    def worked_hours(self) -> Decimal:
        """Worked hours with second precision"""
        return Decimal(self.worked_seconds) / 3600
    
    @property
    def worked_time_readable(self) -> str:
        """Worked time in readable format"""
        hours, remainder = divmod(self.worked_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}h {minutes}m {seconds}s"
    
    @property 
    def has_overtime(self) -> bool:
        """Check if there's overtime (over 8 hours)"""
        return self.worked_seconds > 8 * 3600
    
    @property
    def overtime_seconds(self) -> int:
        """Number of overtime seconds"""
        if self.has_overtime:
            return self.worked_seconds - (8 * 3600)
        return 0
    
    def add_timestamp(self, timestamp: TimeStamp) -> None:
        """Add timestamp to work day"""
        if timestamp.employee_id != self.employee_id:
            raise ValueError("Timestamp employee ID doesn't match work day employee ID")
        if timestamp.timestamp.date() != self.date:
            raise ValueError("Timestamp date doesn't match work day date")
        self.timestamps.append(timestamp)


@dataclass
class WorkMonth:
    """Single employee work month"""
    year: int
    month: int  # 1-12
    employee_id: str
    work_days: List[WorkDay]
    
    def __post_init__(self):
        if not self.employee_id:
            raise ValueError("Employee ID cannot be empty")
        if not (1 <= self.month <= 12):
            raise ValueError("Month must be between 1 and 12")
        if self.year < 1900:
            raise ValueError("Year must be greater than 1900")
        
        # Check that all days belong to this employee and month
        for day in self.work_days:
            if day.employee_id != self.employee_id:
                raise ValueError(f"Work day {day.date} belongs to different employee")
            if day.date.year != self.year or day.date.month != self.month:
                raise ValueError(f"Work day {day.date} doesn't belong to this month")
    
    @property
    def total_worked_seconds(self) -> int:
        """Total worked time in seconds for the month"""
        return sum(day.worked_seconds for day in self.work_days)
    
    @property
    def total_worked_hours(self) -> Decimal:
        """Total worked time in hours for the month"""
        return Decimal(self.total_worked_seconds) / 3600
    
    @property
    def overtime_seconds(self) -> int:
        """Total overtime in seconds for the month"""
        return sum(day.overtime_seconds for day in self.work_days)
    
    @property
    def overtime_hours(self) -> Decimal:
        """Total overtime in hours for the month"""
        return Decimal(self.overtime_seconds) / 3600
    
    @property
    def actual_work_days(self) -> int:
        """Number of days when employee actually worked"""
        return sum(1 for day in self.work_days 
                  if day.status != DayStatus.ABSENT)
    
    @property
    def overtime_days(self) -> int:
        """Number of days with overtime"""
        return sum(1 for day in self.work_days if day.has_overtime)
    
    @property
    def holidays_worked(self) -> int:
        """Number of holidays worked"""
        return sum(1 for day in self.work_days 
                  if day.day_type == DayType.HOLIDAY and 
                     day.status != DayStatus.ABSENT)
    
    @property
    def weekends_worked(self) -> int:
        """Number of weekends worked"""
        return sum(1 for day in self.work_days 
                  if day.day_type == DayType.WEEKEND and 
                     day.status != DayStatus.ABSENT)
    
    def add_work_day(self, day: WorkDay) -> None:
        """Add work day to month"""
        if day.employee_id != self.employee_id:
            raise ValueError("Employee ID doesn't match")
        if day.date.year != self.year or day.date.month != self.month:
            raise ValueError("Day date doesn't belong to this month")
        
        # Check that day with this date doesn't already exist
        for existing_day in self.work_days:
            if existing_day.date == day.date:
                raise ValueError(f"Day {day.date} already exists in this month")
        
        self.work_days.append(day)
    
    def get_work_day(self, date: date) -> Optional[WorkDay]:
        """Get work day by date"""
        for day in self.work_days:
            if day.date == date:
                return day
        return None


@dataclass
class Employee:
    """Company employee"""
    id: str
    first_name: str
    last_name: str
    base_hourly_rate: Decimal  # rubles per hour
    overtime_hourly_rate: Decimal  # rubles per overtime hour
    holiday_hourly_rate: Decimal  # rubles per holiday hour
    weekend_hourly_rate: Decimal  # rubles per weekend hour
    work_months: List[WorkMonth]
    
    def __post_init__(self):
        if not self.id:
            raise ValueError("Employee ID cannot be empty")
        if not self.first_name or not self.last_name:
            raise ValueError("First name and last name cannot be empty")
        if self.base_hourly_rate <= 0:
            raise ValueError("Base hourly rate must be positive")
        if self.overtime_hourly_rate <= 0:
            raise ValueError("Overtime hourly rate must be positive")
        if self.holiday_hourly_rate <= 0:
            raise ValueError("Holiday hourly rate must be positive")
        if self.weekend_hourly_rate <= 0:
            raise ValueError("Weekend hourly rate must be positive")
    
    @property
    def full_name(self) -> str:
        """Employee full name"""
        return f"{self.last_name} {self.first_name}"
    
    def add_work_month(self, month: WorkMonth) -> None:
        """Add work month"""
        if month.employee_id != self.id:
            raise ValueError("Employee ID doesn't match")
        
        # Check that month with this date doesn't already exist
        for existing_month in self.work_months:
            if (existing_month.year == month.year and 
                existing_month.month == month.month):
                raise ValueError(f"Month {month.month}/{month.year} already exists")
        
        self.work_months.append(month)
    
    def get_work_month(self, year: int, month: int) -> Optional[WorkMonth]:
        """Get work month by year and month"""
        for work_month in self.work_months:
            if work_month.year == year and work_month.month == month:
                return work_month
        return None