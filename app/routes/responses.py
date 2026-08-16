from fastapi import APIRouter, HTTPException, status, Depends
from app.schemas import ArticleOut, ArticleUpdate, ArticleCreate, PaymentStatus, SubscriptionRequest,Plan
from app.storage import load_data, save_data
from crew.crew import generate_article
from datetime import datetime,timezone,timedelta
from typing import List
from app.auth import get_current_user
from app.models import User, Payment, Subscription, PLAN_PRICES, PLAN_LIMITS, OVERAGE_PRICES
from app.auth import limiter, generate_payment_reference
from fastapi import Request
from sqlalchemy.orm import Session
from app.database import get_db

ACCOUNT = "214812779958, Grey"

router = APIRouter(prefix = "/generator", tags= ["Generate"],dependencies=[Depends(get_current_user)])
router_1 = APIRouter(prefix="/payments", tags = ["Payments"], dependencies = [Depends(get_current_user)])
router_2 = APIRouter(prefix= "/admin", tags=["Admin"])
router_3 = APIRouter(prefix="/subscriptions", tags = ["Subscriptions"], dependencies = [Depends(get_current_user)])

@router_1.post("/create")
def create_payment(current_user:User = Depends(get_current_user), db:Session=Depends(get_db)):
    reference = generate_payment_reference()
    payment = Payment(
        reference = reference,
        user_id = current_user.id,
        amount_cents = 80000,
        payment_type = "api_access"
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    return {
        "reference" :payment.reference,
        "amount" : "$800.00",
        "status": payment.status,
        "account":ACCOUNT,
        "instructions" :("Send $800 USD to the provided payment account"
                         f"using reference {payment.reference}")
    }




@router.get("", response_model = List[ArticleOut])
@limiter.limit("5/minute")
def get_articles(request:Request,current_user: User = Depends(get_current_user)):
    articles = load_data()
    user_articles = [a for a in articles if a.get("user_id") == current_user.id]
    if user_articles:
        return user_articles
    return []

@router.get("/{article_title}", response_model = ArticleOut, status_code= status.HTTP_200_OK)
def get_article(article_title:str,current_user: User = Depends(get_current_user)):
    articles = load_data()
    for article in articles:
        if article["title"].replace(" ", "").lower().strip() == article_title.replace(" ","").lower().strip() and article.get("user_id") == current_user.id:
            return article
    raise HTTPException(status_code = status.HTTP_404_NOT_FOUND, detail = "Article Not Found..Check Spelling")

@router.post("", response_model = ArticleOut, status_code = status.HTTP_200_OK)
async def create_article(payload: ArticleCreate, current_user: User = Depends(get_current_user), db:Session=Depends(get_db)):
    subscription = db.query(Subscription).filter(Subscription.user_id == current_user.id).first()
    if not subscription:
        raise HTTPException(status_code = status.HTTP_403_FORBIDDEN, detail="You need an active subscription")
    if subscription.expires_at <= datetime.utcnow():
        subscription.status = "expired"
        db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail = "Your Subsription has expired")
    if subscription.status != "active":
        raise HTTPException(status_code = status.HTTP_403_FORBIDDEN, detail="Your subscription is not active")

    limit = PLAN_LIMITS[Plan(subscription.plan)]
    if limit is not None:
        if subscription.articles_used>=limit:
            overage_price = OVERAGE_PRICES[Plan(subscription.plan)]
            reference = generate_payment_reference()
            payment = Payment(
                reference = reference,
                user_id = current_user.id,
                amount_cents = overage_price,
                status = "pending",
                plan = subscription.plan,
                payment_type = "overage"
            )
            return {
                "message":"Monthly article limit reached",
                "amount_cents":overage_price,
                "reference":reference,
                "account":ACCOUNT,
                "instructions":(
                    f"Send ${overage_price/100:.2f} USD"
                    f"using reference {reference}"
                )
            }
    articles = load_data()
    article = await generate_article(payload.topic, datetime.now().strftime("%Y-%m-%d"))
    article["user_id"] = current_user.id 
    if article:
        articles.append(article)
        save_data(articles)
        subscription.articles_used += 1

        return article
    raise HTTPException(status_code = status.HTTP_400_BAD_REQUEST, detail = "Connect to the Internet and try again")

@router.put("/{article_title}",response_model = ArticleOut)
def update_article_title(article_title:str, payload:ArticleUpdate, current_user: User = Depends(get_current_user)):
    articles = load_data()

    for article in articles:
        if article["title"].replace(" ", "").lower().strip() == article_title.replace(" ","").lower().strip() and article.get("user_id") == current_user.id:
            if payload.title is not None:
                article["title"] = payload.title

            save_data(articles)
            return article
        
    raise HTTPException(
        status_code = status.HTTP_404_NOT_FOUND,
        detail = "Article Not Found...Check Spellings"
    )

@router.delete("/{article_title}", status_code= status.HTTP_204_NO_CONTENT)
def delete_article(article_title:str,current_user: User = Depends(get_current_user)):
    articles = load_data()

    for i, article in enumerate(articles):
        if article["title"].replace(" ", "").lower().strip() == article_title.replace(" ","").lower().strip() and article.get("user_id") == current_user.id:
            articles.pop(i)
            save_data(articles)
            return

    raise HTTPException(
        status_code= status.HTTP_404_NOT_FOUND,
        detail = "Article Not Found...Check Spellings"

    )

@router_2.post("/payments/{reference}/approve")
def approve_payment(
    reference:str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail = "Admin access required")
    payment = db.query(Payment).filter(Payment.reference == reference).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    if payment.status == PaymentStatus.paid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment already approved")
    if payment.payment_type != "api_access":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail = "Not an api access payment")
    user = db.query(User).filter(User.id == payment.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail = "User not found")
    payment.status = PaymentStatus.paid
    user.api_access = True
    db.commit()
    return {
        "message":"Payment approved",
        "reference":payment.reference,
        "status":payment.status
    }

@router_2.post("/subscriptions/{reference}/approve")
def approve_subscription(
    reference: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )
    payment = db.query(Payment).filter(
        Payment.reference == reference
    ).first()
    if not payment:
        raise HTTPException(
            status_code=404,
            detail="Payment not found"
        )
    if payment.status == "paid":
        raise HTTPException(
            status_code=400,
            detail="Payment already approved"
        )
    if payment.plan is None:
        raise HTTPException(
            status_code=400,
            detail="This is not a subscription payment"
        )
    if payment.payment_type != "subscription":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail = "Not a subscription payment")
    user = db.query(User).filter(
        User.id == payment.user_id
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    subscription = db.query(Subscription).filter(
        Subscription.user_id == user.id
    ).first()

    if not subscription:
        subscription = Subscription(
            user_id=user.id,
            plan=payment.plan,
            status="active",
            started_at=datetime.now(timezone.utc),
            expires_at=(
                datetime.now(timezone.utc)
                + timedelta(days=30)
            ),
            articles_used=0
        )

        db.add(subscription)
    else:
        subscription.plan = payment.plan
        subscription.status = "active"
        subscription.started_at = datetime.now(timezone.utc)
        subscription.expires_at = (
            datetime.now(timezone.utc)
            + timedelta(days=30)
        )
        subscription.articles_used = 0

    payment.status = "paid"
        
    db.commit()
    db.refresh(subscription)

    return {
        "message": "Subscription activated",
        "plan": subscription.plan,
        "expires_at": subscription.expires_at
    }

@router_2.post("/overages/{reference}/approve")
def approve_overage(reference:str, current_user:User = Depends(get_current_user), db:Session = Depends(get_db)):
    subscription = db.query(Subscription).filter(Subscription.user_id == current_user.id).first()
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403, detail="Admin access required")
    payment = db.query(Payment).filter(Payment.reference == reference).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Payment not found")
    if payment.payment_type != "overage":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail = "Not an overage payment")
    if payment.status == "paid":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Payment already approved")
    payment.status = "paid"
    subscription.articles_used-=1
    db.commit()
    return {
        "message":"Overage payment approved",
        "reference":payment.reference,
        "status":payment.status
    }


@router_3.post("/create")
def create_subscription_payment(
    data: SubscriptionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.api_access:
        raise HTTPException(
            status_code=403,
            detail="Purchase API access before subscribing"
        )
    amount = PLAN_PRICES[data.plan]
    reference = generate_payment_reference()
    payment = Payment(
        reference=reference,
        user_id=current_user.id,
        amount_cents=amount,
        status="pending",
        plan=data.plan.value,
        payment_type = "subscription"
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return {
        "reference": payment.reference,
        "plan": data.plan.value,
        "amount_cents": payment.amount_cents,
        "account":ACCOUNT,
        "status": payment.status,
        "instructions": (
            f"Send ${amount / 100:.2f} USD "
            f"using reference {reference}"
        )
    }

