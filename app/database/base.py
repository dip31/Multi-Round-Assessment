"""
SQLAlchemy declarative base.

All ORM models must inherit from ``Base`` defined here so that
``Base.metadata`` contains every table for migrations and testing.
"""

from sqlalchemy.orm import declarative_base

Base = declarative_base()
