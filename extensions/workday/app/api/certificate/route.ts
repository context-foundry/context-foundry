import { NextRequest, NextResponse } from 'next/server';
import { z } from 'zod';
import { renderToStream } from '@react-pdf/renderer';
import { CertificateTemplate } from '@/components/certificate/CertificateTemplate';
import { CertificateRequest, CertificateData, MILESTONES } from '@/types/progress';
import crypto from 'crypto';

/**
 * POST /api/certificate
 *
 * Generate PDF certificate for milestone achievements.
 * Uses @react-pdf/renderer to create professional certificates.
 * Returns PDF as downloadable blob with unique certificate ID.
 */

// Request validation schema
const CertificateRequestSchema = z.object({
  milestoneId: z.string().min(1, 'Milestone ID is required'),
  userName: z.string().min(1, 'User name is required'),
  patternsCompleted: z.number().min(1).optional(),
  averageScore: z.number().min(0).max(100).optional(),
});

/**
 * Generate unique certificate ID
 * Format: WORKWISE-{MILESTONE}-{TIMESTAMP}-{RANDOM}
 */
function generateCertificateId(milestoneId: string): string {
  const timestamp = Date.now().toString(36).toUpperCase();
  const random = crypto.randomBytes(4).toString('hex').toUpperCase();
  const milestone = milestoneId.replace('milestone-', '').toUpperCase();

  return `WORKWISE-${milestone}-${timestamp}-${random}`;
}

/**
 * Format date for certificate
 */
function formatCertificateDate(date: Date): string {
  const options: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  };
  return date.toLocaleDateString('en-US', options);
}

export async function POST(request: NextRequest) {
  try {
    // Parse and validate request body
    const body = await request.json();
    const validationResult = CertificateRequestSchema.safeParse(body);

    if (!validationResult.success) {
      return NextResponse.json(
        {
          error: 'Invalid request body',
          details: validationResult.error.issues,
        },
        { status: 400 }
      );
    }

    const {
      milestoneId,
      userName,
      patternsCompleted,
      averageScore,
    } = validationResult.data;

    // Find milestone data
    const milestone = MILESTONES.find((m) => m.id === milestoneId);
    if (!milestone) {
      return NextResponse.json(
        { error: `Milestone not found: ${milestoneId}` },
        { status: 404 }
      );
    }

    // Check if milestone is certificate-eligible
    if (!milestone.certificateEligible) {
      return NextResponse.json(
        {
          error: 'This milestone is not eligible for a certificate',
          milestoneId,
        },
        { status: 400 }
      );
    }

    // Generate unique certificate ID
    const certificateId = generateCertificateId(milestoneId);

    // Prepare certificate data
    const certificateData: CertificateData = {
      userName: userName.trim(),
      milestoneName: milestone.name,
      milestoneDescription: milestone.description,
      patternsCompleted: patternsCompleted || milestone.targetCount,
      averageScore: averageScore || 85, // Default if not provided
      completionDate: formatCertificateDate(new Date()),
      certificateId,
    };

    // Log certificate generation
    if (process.env.NODE_ENV === 'development') {
      console.log('[Certificate API]', {
        userName: certificateData.userName,
        milestoneId,
        milestoneName: milestone.name,
        certificateId,
      });
    }

    // Render PDF using React PDF
    const stream = await renderToStream(
      CertificateTemplate({ data: certificateData })
    );

    // Convert stream to buffer
    const chunks: Uint8Array[] = [];
    for await (const chunk of stream) {
      chunks.push(chunk);
    }
    const buffer = Buffer.concat(chunks);

    // Return PDF with proper headers
    return new NextResponse(buffer, {
      status: 200,
      headers: {
        'Content-Type': 'application/pdf',
        'Content-Disposition': `attachment; filename="WorkWise-Certificate-${milestone.name.replace(/\s+/g, '-')}-${certificateId}.pdf"`,
        'Content-Length': buffer.length.toString(),
        'Cache-Control': 'private, no-cache',
      },
    });
  } catch (error) {
    console.error('[Certificate API] Error:', error);

    // Handle specific error types
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        {
          error: 'Schema validation failed',
          details: error.issues,
        },
        { status: 400 }
      );
    }

    if (error instanceof Error) {
      // Check for PDF rendering errors
      if (error.message.includes('render')) {
        return NextResponse.json(
          {
            error: 'Failed to render PDF certificate',
            message: error.message,
          },
          { status: 500 }
        );
      }
    }

    return NextResponse.json(
      {
        error: 'Failed to generate certificate',
        message: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}
