import { Pattern, PatternCollection, PatternCollectionSchema, PatternFilterCriteria } from '@/types/pattern';
import patternsData from '@/patterns/workday-expertise.json';

/**
 * PatternParser - Centralized pattern data access and filtering
 *
 * Provides methods to parse, filter, and search Workday expertise patterns.
 * All pattern data is validated against Zod schemas on initialization.
 */
export class PatternParser {
  private patterns: Pattern[];
  private categories: string[];
  private modules: string[];

  constructor() {
    // Transform workday-expertise.json format to Pattern format
    const transformedPatterns = (patternsData.patterns as any[]).map((p: any) => ({
      id: p.pattern_id,
      name: this.generatePatternName(p.pattern_id),
      category: p.category,
      module: p.node_types?.[0] || 'General',
      applies_to: p.applies_to || [],
      description: p.description,
      best_practices: p.best_practices || [],
      anti_patterns: p.anti_patterns || [],
      examples: p.common_issues?.map((i: any) => i.description) || [],
      related_patterns: [],
      tags: [...(p.applies_to || []), p.category],
      difficulty: this.inferDifficulty(p),
      estimated_time_minutes: this.estimateTime(p),
    }));

    // Validate transformed data
    const validated = PatternCollectionSchema.parse({
      patterns: transformedPatterns,
      metadata: patternsData.metadata,
    });

    this.patterns = validated.patterns;
    this.categories = this.extractUniqueCategories();
    this.modules = this.extractUniqueModules();
  }

  private generatePatternName(patternId: string): string {
    // Convert pattern-id to Title Case Name
    return patternId
      .replace(/^workday-/, '')
      .split('-')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  }

  private inferDifficulty(pattern: any): 'beginner' | 'intermediate' | 'advanced' {
    const bestPracticesCount = pattern.best_practices?.length || 0;
    const antiPatternsCount = pattern.anti_patterns?.length || 0;
    const issuesCount = pattern.common_issues?.length || 0;
    const complexity = bestPracticesCount + antiPatternsCount + issuesCount;

    if (complexity < 5) return 'beginner';
    if (complexity < 10) return 'intermediate';
    return 'advanced';
  }

  private estimateTime(pattern: any): number {
    const bestPracticesCount = pattern.best_practices?.length || 0;
    const antiPatternsCount = pattern.anti_patterns?.length || 0;
    // 5 minutes per best practice + 3 minutes per anti-pattern
    return Math.max(15, (bestPracticesCount * 5) + (antiPatternsCount * 3));
  }

  private extractUniqueCategories(): string[] {
    const cats = new Set(this.patterns.map(p => p.category));
    return Array.from(cats).sort();
  }

  private extractUniqueModules(): string[] {
    const mods = new Set(this.patterns.map(p => p.module).filter(Boolean));
    return Array.from(mods).sort();
  }

  /**
   * Parse and return all patterns
   * @returns Array of all patterns
   */
  public parsePatterns(): Pattern[] {
    return this.patterns;
  }

  /**
   * Get a single pattern by ID
   * @param id - Pattern ID
   * @returns Pattern if found, undefined otherwise
   */
  public getPatternById(id: string): Pattern | undefined {
    return this.patterns.find((pattern) => pattern.id === id);
  }

  /**
   * Get all patterns in a specific category
   * @param category - Category name
   * @returns Array of patterns in the category
   */
  public getPatternsByCategory(category: string): Pattern[] {
    return this.patterns.filter((pattern) => pattern.category === category);
  }

  /**
   * Get all patterns in a specific module
   * @param module - Module name
   * @returns Array of patterns in the module
   */
  public getPatternsByModule(module: string): Pattern[] {
    return this.patterns.filter((pattern) => pattern.module === module);
  }

  /**
   * Search patterns with multiple filter criteria
   * @param criteria - Filter criteria
   * @returns Array of patterns matching all criteria
   */
  public searchPatterns(criteria: PatternFilterCriteria): Pattern[] {
    let results = this.patterns;

    // Filter by category
    if (criteria.category) {
      results = results.filter((pattern) => pattern.category === criteria.category);
    }

    // Filter by module
    if (criteria.module) {
      results = results.filter((pattern) => pattern.module === criteria.module);
    }

    // Filter by difficulty
    if (criteria.difficulty) {
      results = results.filter((pattern) => pattern.difficulty === criteria.difficulty);
    }

    // Filter by tags
    if (criteria.tags && criteria.tags.length > 0) {
      results = results.filter((pattern) =>
        pattern.tags?.some((tag) => criteria.tags!.includes(tag))
      );
    }

    // Filter by applies_to
    if (criteria.appliesTo) {
      results = results.filter((pattern) =>
        pattern.applies_to.includes(criteria.appliesTo!)
      );
    }

    // Filter by search query (searches name, description, best_practices, anti_patterns)
    if (criteria.searchQuery) {
      const query = criteria.searchQuery.toLowerCase();
      results = results.filter((pattern) => {
        const searchableText = [
          pattern.name,
          pattern.description,
          ...(pattern.best_practices || []),
          ...(pattern.anti_patterns || []),
          ...(pattern.examples || []),
        ].join(' ').toLowerCase();

        return searchableText.includes(query);
      });
    }

    return results;
  }

  /**
   * Get all available categories
   * @returns Array of category names
   */
  public getCategories(): string[] {
    return this.categories;
  }

  /**
   * Get all available modules
   * @returns Array of module names
   */
  public getModules(): string[] {
    return this.modules;
  }

  /**
   * Get total pattern count
   * @returns Total number of patterns
   */
  public getTotalCount(): number {
    return this.patterns.length;
  }

  /**
   * Get patterns by difficulty level
   * @param difficulty - Difficulty level
   * @returns Array of patterns with the specified difficulty
   */
  public getPatternsByDifficulty(difficulty: 'beginner' | 'intermediate' | 'advanced'): Pattern[] {
    return this.patterns.filter((pattern) => pattern.difficulty === difficulty);
  }

  /**
   * Get related patterns for a given pattern ID
   * @param patternId - Pattern ID
   * @returns Array of related patterns
   */
  public getRelatedPatterns(patternId: string): Pattern[] {
    const pattern = this.getPatternById(patternId);
    if (!pattern || !pattern.related_patterns) {
      return [];
    }

    return pattern.related_patterns
      .map((id) => this.getPatternById(id))
      .filter((p): p is Pattern => p !== undefined);
  }
}

// Export singleton instance
export const patternParser = new PatternParser();
