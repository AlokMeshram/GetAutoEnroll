"""
Cluster Configuration

This file contains all business rules related to
cluster interpretation, outreach priority, and
recommended communication channels.

If cluster definitions change, only this file
needs to be updated.
"""

CLUSTER_CONFIG = {

    0: {
        "persona": "Skilling Active but Employment Gap",
        "priority": "Medium",
        "recommended_channels": [
            "WhatsApp",
            "Email",
            "Skill Workshops"
        ]
    },

    1: {
        "persona": "Emerging Growth States",
        "priority": "Medium",
        "recommended_channels": [
            "WhatsApp",
            "SMS",
            "Community Meetings"
        ]
    },

    2: {
        "persona": "Highly Educated Urban Workforce",
        "priority": "Low",
        "recommended_channels": [
            "WhatsApp",
            "Email",
            "LinkedIn",
            "Career Webinars"
        ]
    },

    3: {
        "persona": "High Priority Rural Youth",
        "priority": "High",
        "recommended_channels": [
            "SMS",
            "WhatsApp",
            "Community Champions",
            "Posters",
            "Village Awareness Drives"
        ]
    }

}