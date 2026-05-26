-- Migration: Add approval workflow fields to license_requests and queue_items tables
-- Add new columns to license_requests for approval stage tracking
ALTER TABLE license_requests
ADD approval_stage NVARCHAR(50) DEFAULT 'pending_account_owner',
    last_approver_user_id INT NULL,
    last_approval_time DATETIME2 NULL,
    approval_notes NVARCHAR(MAX) NULL;

-- Create index for approval_stage for query performance
CREATE INDEX idx_license_requests_approval_stage ON license_requests(approval_stage);

-- Add new columns to queue_items for approval stage tracking
ALTER TABLE queue_items
ADD approval_stage NVARCHAR(50) NULL,
    assigned_approval_role NVARCHAR(50) NULL;

-- Create the approval_histories table for tracking approval actions
CREATE TABLE approval_histories (
    id INT NOT NULL IDENTITY(1,1) PRIMARY KEY,
    request_id INT NOT NULL FOREIGN KEY REFERENCES license_requests(id),
    approval_stage NVARCHAR(50) NOT NULL,
    approver_user_id INT NULL FOREIGN KEY REFERENCES users(id),
    approver_role NVARCHAR(50) NOT NULL,
    action NVARCHAR(20) NOT NULL,
    notes NVARCHAR(MAX) NULL,
    created_at DATETIME2 NOT NULL DEFAULT GETDATE()
);

-- Create indexes for approval_histories
CREATE INDEX idx_approval_histories_request_id ON approval_histories(request_id);
CREATE INDEX idx_approval_histories_created_at ON approval_histories(created_at);
