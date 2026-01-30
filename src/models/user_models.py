"""Pydantic models for user profiles (no consent required)."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class UserProfileBase(BaseModel):
    """Base user profile fields (no consent required)."""

    sender_id: str = Field(..., description="Facebook User ID (PSID)")
    page_id: str = Field(..., description="Facebook Page ID")

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    profile_pic: Optional[str] = None
    locale: Optional[str] = None
    timezone: Optional[int] = None

    location_lat: Optional[float] = None
    location_long: Optional[float] = None
    location_title: Optional[str] = None
    location_address: Optional[str] = None


class UserProfileCreate(UserProfileBase):
    """Model for creating a new user profile."""

    pass


class UserProfileUpdate(BaseModel):
    """Model for updating user profile (all fields optional)."""

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    profile_pic: Optional[str] = None
    locale: Optional[str] = None
    timezone: Optional[int] = None
    location_lat: Optional[float] = None
    location_long: Optional[float] = None
    location_title: Optional[str] = None
    location_address: Optional[str] = None


class UserProfile(UserProfileBase):
    """Full user profile with database fields."""

    id: str
    first_interaction_at: datetime
    last_interaction_at: datetime
    total_messages: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FacebookUserInfo(BaseModel):
    """User info from Facebook Graph API (public profile fields only)."""

    id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    profile_pic: Optional[str] = None
    locale: Optional[str] = None
    timezone: Optional[int] = None


class FacebookLocation(BaseModel):
    """Location shared by user via Messenger."""

    lat: float
    long: float
    title: Optional[str] = None
    address: Optional[str] = None
    url: Optional[str] = None
