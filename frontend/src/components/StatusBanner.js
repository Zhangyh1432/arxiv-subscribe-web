import React from 'react';

function StatusBanner({ status, message, resultsReadyKey, onViewResults }) {
    // Special case: When results are ready, show a dedicated button.
    if (status === 'review_ready' && resultsReadyKey) {
        return (
            <div className="alert alert-success sticky-top shadow-sm mb-4 d-flex justify-content-between align-items-center">
                <span>
                    <strong>{message}</strong> Papers are ready for review.
                </span>
                <button className="btn btn-light fw-bold" onClick={() => onViewResults(resultsReadyKey)}>
                    View Results &rarr;
                </button>
            </div>
        );
    }

    // Do not render for idle status, or if the main purpose (review_ready) is handled above.
    if (status === 'idle' || status === 'review_ready') {
        return null;
    }

    let alertType = 'alert-info';
    if (status === 'error') {
        alertType = 'alert-danger';
    } else if (status === 'success') {
        alertType = 'alert-success';
    } else if (status === 'running') {
        alertType = 'alert-primary';
    }

    return (
        <div className={`alert ${alertType} sticky-top shadow-sm mb-4`}>
            <strong>Status:</strong> {status} <br />
            <strong>Message:</strong> {message}
        </div>
    );
}

export default StatusBanner;
