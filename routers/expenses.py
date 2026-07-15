from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from db import get_session
from models import Expense
from crud import get_expenses, create_expense, delete_expense
from typing import List

router = APIRouter(prefix="/api/expenses", tags=["Expenses"])

@router.get("/", response_model=List[Expense])
def read_expenses(session: Session = Depends(get_session)):
    return get_expenses(session)

@router.post("/", response_model=Expense)
def add_expense(expense: Expense, session: Session = Depends(get_session)):
    return create_expense(session, expense)

@router.delete("/{expense_id}")
def remove_expense(expense_id: int, session: Session = Depends(get_session)):
    success = delete_expense(session, expense_id)
    if not success:
        raise HTTPException(status_code=404, detail="Expense not found")
    return {"message": "Expense deleted successfully"}
