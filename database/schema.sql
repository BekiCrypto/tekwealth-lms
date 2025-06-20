-- Database schema for the MLM E-Learning Platform

-- Users table to store user information
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'Guest', -- Guest, Subscriber, Admin, MLM Partner
    referral_code VARCHAR(255) UNIQUE,
    referred_by_id INTEGER REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Courses table to store course details
CREATE TABLE courses (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    level VARCHAR(50) NOT NULL, -- Beginner, Pro, Advanced
    category VARCHAR(50) NOT NULL, -- Forex, Crypto, Stock, Commodities
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Course modules table to store individual modules for each course
CREATE TABLE course_modules (
    id SERIAL PRIMARY KEY,
    course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    module_order INTEGER NOT NULL, -- To define the sequence of modules
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Module content table to store the actual content of each module (video, PDF, quiz)
CREATE TABLE module_content (
    id SERIAL PRIMARY KEY,
    module_id INTEGER REFERENCES course_modules(id) ON DELETE CASCADE,
    content_type VARCHAR(50) NOT NULL, -- video, pdf, quiz
    content_url VARCHAR(255), -- URL to video or PDF file
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Quizzes table to store quiz details associated with a module
CREATE TABLE quizzes (
    id SERIAL PRIMARY KEY,
    module_id INTEGER REFERENCES course_modules(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Quiz questions table to store individual questions for each quiz
CREATE TABLE quiz_questions (
    id SERIAL PRIMARY KEY,
    quiz_id INTEGER REFERENCES quizzes(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    question_type VARCHAR(50) DEFAULT 'multiple_choice', -- multiple_choice, true_false
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Question options table to store options for multiple-choice questions
CREATE TABLE question_options (
    id SERIAL PRIMARY KEY,
    question_id INTEGER REFERENCES quiz_questions(id) ON DELETE CASCADE,
    option_text TEXT NOT NULL,
    is_correct BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- User progress table to track user completion of module content
CREATE TABLE user_progress (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    content_id INTEGER REFERENCES module_content(id) ON DELETE CASCADE, -- Link to the specific content item
    completed_at TIMESTAMP WITH TIME ZONE, -- Timestamp when the content was completed
    playback_position INTEGER, -- For videos, to resume playback
    score INTEGER, -- For quizzes
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, content_id) -- Ensures a user has only one progress entry per content item
);

-- Subscriptions table to manage user subscriptions
CREATE TABLE subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    plan_name VARCHAR(100) NOT NULL, -- e.g., Monthly, Yearly, Lifetime
    start_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    end_date TIMESTAMP WITH TIME ZONE, -- Null for lifetime or non-expiring plans
    status VARCHAR(50) NOT NULL DEFAULT 'active', -- active, expired, cancelled
    payment_gateway_subscription_id VARCHAR(255), -- Stores subscription ID from payment gateway like Stripe
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Payments table to record payment transactions
CREATE TABLE payments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    subscription_id INTEGER REFERENCES subscriptions(id) ON DELETE CASCADE, -- Link to the subscription this payment is for
    amount DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'USD',
    payment_gateway VARCHAR(50) NOT NULL, -- e.g., Stripe, Chapa, Telebirr
    transaction_id VARCHAR(255) UNIQUE NOT NULL, -- Unique ID from the payment gateway
    status VARCHAR(50) NOT NULL DEFAULT 'succeeded', -- succeeded, pending, failed
    payment_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Referrals table to track MLM referrals and commissions
CREATE TABLE referrals (
    id SERIAL PRIMARY KEY,
    referrer_id INTEGER REFERENCES users(id) ON DELETE CASCADE, -- The user who made the referral
    referred_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, -- The user who was referred
    commission_amount DECIMAL(10, 2),
    commission_status VARCHAR(50) DEFAULT 'pending', -- pending, approved, paid, rejected
    referral_level INTEGER NOT NULL, -- Indicates the level of referral (1, 2, or 3)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (referrer_id, referred_user_id) -- Ensures a user cannot refer the same user multiple times
);

-- Certificates table to store information about issued course completion certificates
CREATE TABLE certificates (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
    certificate_url VARCHAR(255) NOT NULL, -- URL to the generated certificate PDF
    issued_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, course_id) -- Ensures a user gets only one certificate per course
);

-- Indexes for frequently queried columns
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_courses_category ON courses(category);
CREATE INDEX idx_courses_level ON courses(level);
CREATE INDEX idx_user_progress_user_content ON user_progress(user_id, content_id);
CREATE INDEX idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX idx_payments_user_id ON payments(user_id);
CREATE INDEX idx_referrals_referrer_id ON referrals(referrer_id);
CREATE INDEX idx_referrals_referred_user_id ON referrals(referred_user_id);
CREATE INDEX idx_certificates_user_course ON certificates(user_id, course_id);

-- Trigger function to update 'updated_at' timestamp automatically
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply the trigger to all tables that have an 'updated_at' column
DO $$
DECLARE
    t_name TEXT;
BEGIN
    FOR t_name IN (SELECT table_name FROM information_schema.columns WHERE column_name = 'updated_at')
    LOOP
        EXECUTE format('CREATE TRIGGER update_%s_updated_at
                        BEFORE UPDATE ON %I
                        FOR EACH ROW
                        EXECUTE FUNCTION update_updated_at_column();', t_name, t_name);
    END LOOP;
END;
$$;
