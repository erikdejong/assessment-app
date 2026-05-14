from sqlalchemy import Column, String, Boolean
from database import Base

class User(Base):
    __tablename__ = "users"     
    __table_args__ = {"schema": "app"}  

    username = Column(String, primary_key=True, index=True)
    password = Column(String, nullable=False)  