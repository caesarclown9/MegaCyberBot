import re
from typing import Dict, Any, Optional
from enum import Enum


class ArticleCategory(Enum):
    VULNERABILITIES = "vulnerabilities"
    GENERAL = "general"


class ArticleCategorizer:
    """Categorizes articles into vulnerabilities or general cybersecurity news."""
    
    # Patterns that strongly indicate vulnerability-related content
    VULNERABILITY_PATTERNS = [
        r'CVE-\d{4}-\d{4,}',  # CVE identifiers
        r'zero[- ]?day',
        r'0[- ]?day',
        r'\bRCE\b',  # Remote Code Execution
        r'remote code execution',
        r'privilege escalation',
        r'buffer overflow',
        r'SQL injection',
        r'\bSQLi\b',
        r'cross[- ]?site scripting',
        r'\bXSS\b',
        r'\bCSRF\b',
        r'cross[- ]?site request forgery',
        r'security patch(?:es)?',
        r'security update(?:s)?',
        r'critical vulnerability',
        r'vulnerability disclosed',
        r'exploit(?:s|ed|able)?',
        r'proof[- ]?of[- ]?concept',
        r'\bPoC\b',
        r'authentication bypass',
        r'security flaw(?:s)?',
        r'security bug(?:s)?',
        r'patch(?:ed|es|ing)? vulnerability',
        r'fix(?:ed|es|ing)? vulnerability',
        r'vulnerability fix(?:ed|es)?',
        r'actively exploited',
        r'in[- ]?the[- ]?wild exploit',
        r'emergency patch',
        r'critical patch',
        r'security advisory',
        r'vulnerability report',
        r'CVSS score',
        r'attack vector',
        r'denial[- ]?of[- ]?service',
        r'\bDoS\b',
        r'\bDDoS\b',
        r'memory corruption',
        r'heap overflow',
        r'stack overflow',
        r'use[- ]?after[- ]?free',
        r'race condition',
        r'arbitrary code execution',
        r'local privilege escalation',
        r'\bLPE\b',
        r'sandbox escape',
        r'security bypass',
        r'information disclosure',
        r'data exposure',
        r'unauthorized access',
        r'security hole',
    ]
    
    # Keywords that suggest general cybersecurity news
    GENERAL_PATTERNS = [
        r'data breach(?:es)?',
        r'cyber ?attack',
        r'ransomware',
        r'malware',
        r'phishing',
        r'security trend',
        r'cybersecurity report',
        r'threat actor',
        r'APT\d+',  # Advanced Persistent Threat groups
        r'security research',
        r'security tool',
        r'security framework',
        r'compliance',
        r'GDPR',
        r'security audit',
        r'penetration test',
        r'bug bounty',
        r'security conference',
        r'security training',
        r'cybercrime',
        r'dark ?web',
        r'security startup',
        r'acquisition',
        r'security funding',
        r'security policy',
        r'security strategy',
        r'incident response',
        r'threat intelligence',
        r'security operations',
        r'SOC',  # Security Operations Center
        r'SIEM',  # Security Information and Event Management
    ]
    
    # Vulnerability-specific sources or sections
    VULNERABILITY_SOURCES = [
        'nvd.nist.gov',
        'cve.mitre.org',
        'exploit-db.com',
        'packetstormsecurity.com',
        'seclists.org',
        'vuldb.com'
    ]
    
    def __init__(self):
        # Compile patterns for better performance
        self.vulnerability_regex = re.compile(
            '|'.join(self.VULNERABILITY_PATTERNS), 
            re.IGNORECASE
        )
        self.general_regex = re.compile(
            '|'.join(self.GENERAL_PATTERNS), 
            re.IGNORECASE
        )
    
    def categorize(self, article: Dict[str, Any]) -> ArticleCategory:
        """
        Categorize an article based on its content.
        
        Args:
            article: Dictionary containing article data with keys like 'title', 
                    'description', 'url', 'source'
        
        Returns:
            ArticleCategory.VULNERABILITIES or ArticleCategory.GENERAL
        """
        # Combine title and description for analysis
        title = article.get('title', '') or ''
        description = article.get('description', '') or ''
        url = article.get('url', '') or ''
        source = article.get('source', '') or ''
        
        # Combine all text for analysis
        combined_text = f"{title} {description}".lower()
        
        # Check if URL is from vulnerability-specific source
        for vuln_source in self.VULNERABILITY_SOURCES:
            if vuln_source in url.lower():
                return ArticleCategory.VULNERABILITIES
        
        # Count vulnerability and general pattern matches
        vuln_matches = len(self.vulnerability_regex.findall(combined_text))
        general_matches = len(self.general_regex.findall(combined_text))
        
        # Strong indicators for vulnerabilities
        if 'CVE-' in title or 'CVE-' in description:
            return ArticleCategory.VULNERABILITIES
        
        # If vulnerability patterns significantly outweigh general patterns
        if vuln_matches > 0 and vuln_matches >= general_matches * 1.5:
            return ArticleCategory.VULNERABILITIES
        
        # Check for vulnerability keywords in title (higher weight)
        title_lower = title.lower()
        high_priority_vuln_keywords = [
            'vulnerability', 'exploit', 'zero-day', '0-day', 
            'patch', 'security update', 'cve', 'rce', 
            'sql injection', 'xss', 'buffer overflow'
        ]
        
        for keyword in high_priority_vuln_keywords:
            if keyword in title_lower:
                return ArticleCategory.VULNERABILITIES
        
        # Default to general if uncertain
        return ArticleCategory.GENERAL
    
    def get_category_score(self, article: Dict[str, Any]) -> Dict[str, float]:
        """
        Get confidence scores for each category.
        
        Returns:
            Dictionary with scores for each category (0.0 to 1.0)
        """
        title = article.get('title', '') or ''
        description = article.get('description', '') or ''
        combined_text = f"{title} {description}".lower()
        
        vuln_matches = len(self.vulnerability_regex.findall(combined_text))
        general_matches = len(self.general_regex.findall(combined_text))
        
        total_matches = vuln_matches + general_matches
        if total_matches == 0:
            return {
                ArticleCategory.VULNERABILITIES.value: 0.0,
                ArticleCategory.GENERAL.value: 0.5  # Default to general
            }
        
        return {
            ArticleCategory.VULNERABILITIES.value: vuln_matches / total_matches,
            ArticleCategory.GENERAL.value: general_matches / total_matches
        }