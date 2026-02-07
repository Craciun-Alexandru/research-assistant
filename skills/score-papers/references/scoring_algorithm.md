# Paper Scoring Algorithm

Detailed formulas and heuristics for paper relevance scoring.

## Quick Scoring Formula - used by quick-scorer
Total Score = CategoryScore + KeywordScore + InterestScore + NoveltyBonus - AvoidancePenalty

### Category Score (0-5 points)
```pseudocode
FUNCTION calculate_category_score(paper_categories, user_areas)
    score ← 0
    
    FOR each category IN paper_categories
        IF category EXISTS IN user_areas
            weight ← user_areas[category].weight
            
            IF category IS paper_categories[0]  // primary category
                score ← score + (5 × weight)
            ELSE                                 // secondary category
                score ← score + (2.5 × weight)
            END IF
        END IF
    END FOR
    
    RETURN minimum(score, 5)  // cap the score at 5
END FUNCTION
```

### Keyword Score (0-3 points)
```pseudocode
FUNCTION calculate_keyword_score(paper, user_keywords)
    title_lower ← lowercase(paper["title"])
    abstract_lower ← lowercase(paper["abstract"])
    
    score ← 0
    
    FOR each keyword IN user_keywords
        keyword_lower ← lowercase(keyword)
        
        IF keyword_lower IS SUBSTRING OF title_lower
            score ← score + 2
        ELSE IF keyword_lower IS SUBSTRING OF abstract_lower
            score ← score + 0.5
        END IF
    END FOR
    
    RETURN minimum(score, 3)  // cap at 3
END FUNCTION
```

### Interest Score (0-2 points)
```
FUNCTION calculate_interest_score(paper, user_interests)
    title ← paper['title']
    abstract_snippet ← first 500 characters of paper['abstract']
    
    interests_list ← join user_interests with newline, each line prefixed with "- "
    
    prompt ← formatted multi-line string:
        "Paper: {title}"
        "Abstract: {abstract_snippet}"
        ""
        "User interests:"
        {interests_list}
        ""
        "How well does this paper align with the user's research interests?"
        "Score: 0 (no match), 1 (partial match), or 2 (strong match)"
    
    llm_response ← call LLM model with prompt  // model returns integer 0, 1, or 2
    
    RETURN llm_response
END FUNCTION
```

### Novelty Bonus (0-1 points)
```pseudocode
FUNCTION calculate_novelty_bonus(paper)
    indicators ← [
        "novel",
        "new approach",
        "first time",
        "theorem",
        "proof",
        "we prove",
        "breakthrough",
        "significant advance"
    ]
    
    text ← lowercase(paper["title"] + " " + paper["abstract"])
    
    matches ← 0
    FOR each indicator IN indicators
        IF indicator IS SUBSTRING OF text
            matches ← matches + 1
        END IF
    END FOR
    
    IF matches >= 2
        RETURN 1
    ELSE
        RETURN 0
    END IF
END FUNCTION
```

### Avoidance Penalty (0-3 points)
```pseudocode
FUNCTION calculate_avoidance_penalty(paper, avoid_criteria)
    penalty ← 0
    
    FOR each criterion IN avoid_criteria
        criterion_lower ← lowercase(criterion)
        
        IF "empirical" IS SUBSTRING OF criterion_lower
            benchmark_terms ← ["benchmark", "evaluation", "survey", "comparison"]
            theory_terms ← ["theorem", "proof", "theory", "theoretical"]
            
            has_benchmark ← FALSE
            FOR each term IN benchmark_terms
                IF term IS SUBSTRING OF lowercase(paper["title"])
                    has_benchmark ← TRUE
                END IF
            END FOR
            
            has_theory ← FALSE
            FOR each term IN theory_terms
                IF term IS SUBSTRING OF lowercase(paper["abstract"])
                    has_theory ← TRUE
                END IF
            END FOR
            
            IF has_benchmark AND NOT has_theory
                penalty ← penalty + 2
            END IF
        END IF
        
        IF "engineering" IS SUBSTRING OF criterion_lower
            engineering_terms ← ["implementation", "system", "framework", "tool"]
            
            has_engineering ← FALSE
            FOR each term IN engineering_terms
                IF term IS SUBSTRING OF lowercase(paper["title"])
                    has_engineering ← TRUE
                END IF
            END FOR
            
            has_theory ← "theorem" IS SUBSTRING OF lowercase(paper["abstract"])
            
            IF has_engineering AND NOT has_theory
                penalty ← penalty + 1
            END IF
        END IF
    END FOR
    
    RETURN minimum(penalty, 3)  // cap at 3
END FUNCTION
```

## Deep Scoring Considerations - to be considered by deep-reviewer

For deep-reviewer mode, consider:

1. **Methodological Rigor**: Does the paper use sound methodology?
2. **Contribution Significance**: Is this an incremental or major advance?
3. **Cross-Field Potential**: Does it bridge multiple research areas?
4. **Reproducibility**: Are results clearly described and reproducible?
5. **Writing Quality**: Is the paper well-written and clear?

These factors inform the final selection but aren't numerically scored.
