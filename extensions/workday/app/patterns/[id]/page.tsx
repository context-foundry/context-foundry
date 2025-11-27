import { notFound } from 'next/navigation';
import { PatternDetail } from '@/components/patterns/PatternDetail';
import { Pattern } from '@/types/pattern';
import Link from 'next/link';
import { ArrowLeft, PlayCircle } from 'lucide-react';

// Mock pattern data - replace with actual data fetch
async function getPattern(id: string): Promise<Pattern | null> {
  // This would typically fetch from a database or API
  const mockPatterns: Record<string, Pattern> = {
    'pattern-1': {
      id: 'pattern-1',
      name: 'Security Group Design',
      category: 'Security',
      module: 'HCM',
      applies_to: ['HCM', 'Finance', 'Payroll'],
      description: 'Best practices for designing security groups in Workday to ensure proper access control and segregation of duties.',
      best_practices: [
        'Use role-based access control (RBAC) to assign permissions based on job functions',
        'Implement segregation of duties to prevent conflicts of interest',
        'Create security groups with clear naming conventions',
        'Document security group purposes and membership criteria',
        'Regularly review and audit security group memberships',
        'Use constrained security groups to limit access to specific data',
      ],
      anti_patterns: [
        'Granting excessive permissions to security groups',
        'Using overly broad security groups that violate least privilege',
        'Creating security groups without proper documentation',
        'Failing to regularly review security group memberships',
      ],
      examples: [
        'Example: Create a "Finance Approvers" security group that only includes users who need to approve financial transactions',
        'Example: Use constrained security groups to limit payroll access to only employees in specific organizations',
      ],
      related_patterns: ['Role-Based Security', 'Access Control', 'Security Audit'],
      tags: ['security', 'access-control', 'best-practice'],
      difficulty: 'intermediate',
      estimated_time_minutes: 30,
    },
    'pattern-2': {
      id: 'pattern-2',
      name: 'Business Process Configuration',
      category: 'Business Process',
      module: 'HCM',
      applies_to: ['HCM', 'Talent'],
      description: 'Guidelines for configuring efficient and effective business processes in Workday.',
      best_practices: [
        'Define clear approval chains with appropriate escalation paths',
        'Use conditional routing to streamline processes',
        'Configure email notifications at key steps',
        'Set appropriate due dates and reminders',
        'Test business processes thoroughly before deployment',
      ],
      anti_patterns: [
        'Creating overly complex approval chains',
        'Not setting due dates or reminders',
        'Skipping testing in sandbox environments',
      ],
      examples: [
        'Example: Configure a hire business process with conditional routing based on job level',
      ],
      related_patterns: ['Workflow Design', 'Approval Configuration'],
      tags: ['business-process', 'workflow', 'configuration'],
      difficulty: 'advanced',
      estimated_time_minutes: 45,
    },
  };

  return mockPatterns[id] || null;
}

export default async function PatternDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const pattern = await getPattern(params.id);

  if (!pattern) {
    notFound();
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Back Button */}
      <Link
        href="/patterns"
        className="inline-flex items-center gap-2 text-blue-600 hover:text-blue-700 mb-6 min-h-[44px]"
        aria-label="Back to patterns"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Back to Patterns
      </Link>

      {/* Pattern Detail */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 md:p-8 mb-6">
        <PatternDetail pattern={pattern} />
      </div>

      {/* Learning Actions */}
      <div className="bg-gradient-to-br from-blue-50 to-purple-50 rounded-lg border border-blue-200 p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">
          Ready to Learn?
        </h2>
        <p className="text-gray-700 mb-6">
          Complete the interactive learning modules to master this pattern
        </p>

        <div className="flex flex-col sm:flex-row gap-4">
          <Link
            href={`/learn/${pattern.id}?tab=quiz`}
            className="inline-flex items-center justify-center gap-2 px-6 py-3 text-base font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 shadow-sm hover:shadow-md transition-all min-h-[44px]"
            aria-label="Start quiz"
          >
            <PlayCircle className="h-5 w-5" aria-hidden="true" />
            Start Quiz
          </Link>
          <Link
            href={`/learn/${pattern.id}?tab=scenario`}
            className="inline-flex items-center justify-center gap-2 px-6 py-3 text-base font-semibold text-blue-600 bg-white border-2 border-blue-600 rounded-lg hover:bg-blue-50 transition-all min-h-[44px]"
            aria-label="Try scenario"
          >
            Try Scenario
          </Link>
          <Link
            href={`/learn/${pattern.id}?tab=fill-blank`}
            className="inline-flex items-center justify-center gap-2 px-6 py-3 text-base font-semibold text-blue-600 bg-white border-2 border-blue-600 rounded-lg hover:bg-blue-50 transition-all min-h-[44px]"
            aria-label="Practice exercises"
          >
            Practice Exercises
          </Link>
        </div>
      </div>
    </div>
  );
}

// Generate static params for static generation (optional)
export async function generateStaticParams() {
  // Return array of pattern IDs
  return [
    { id: 'pattern-1' },
    { id: 'pattern-2' },
  ];
}
