import React from 'react';
import { Document, Page, Text, View, StyleSheet } from '@react-pdf/renderer';
import { CertificateData } from '@/types/progress';

/**
 * Certificate Template Component
 *
 * Professional PDF certificate using @react-pdf/renderer.
 * Designed for milestone achievements in the WorkWise learning platform.
 */

const styles = StyleSheet.create({
  page: {
    padding: 60,
    backgroundColor: '#ffffff',
    fontFamily: 'Helvetica',
  },
  border: {
    border: '4pt solid #1e40af',
    borderRadius: 8,
    padding: 40,
    height: '100%',
  },
  innerBorder: {
    border: '1pt solid #3b82f6',
    borderRadius: 4,
    padding: 30,
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'space-between',
  },
  header: {
    textAlign: 'center',
    marginBottom: 30,
  },
  title: {
    fontSize: 36,
    fontFamily: 'Helvetica-Bold',
    color: '#1e40af',
    marginBottom: 10,
  },
  subtitle: {
    fontSize: 14,
    color: '#64748b',
    marginTop: 5,
  },
  content: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'center',
    alignItems: 'center',
    textAlign: 'center',
  },
  presentedTo: {
    fontSize: 12,
    color: '#64748b',
    marginBottom: 10,
    textTransform: 'uppercase',
    letterSpacing: 2,
  },
  userName: {
    fontSize: 32,
    fontFamily: 'Helvetica-Bold',
    color: '#0f172a',
    marginBottom: 20,
    borderBottom: '2pt solid #e2e8f0',
    paddingBottom: 10,
  },
  achievement: {
    fontSize: 14,
    color: '#475569',
    marginBottom: 5,
    lineHeight: 1.6,
  },
  milestoneName: {
    fontSize: 20,
    fontFamily: 'Helvetica-Bold',
    color: '#1e40af',
    marginTop: 10,
    marginBottom: 5,
  },
  milestoneDescription: {
    fontSize: 12,
    color: '#64748b',
    marginBottom: 20,
  },
  stats: {
    display: 'flex',
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 40,
    marginTop: 20,
    marginBottom: 20,
  },
  statBox: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
  },
  statValue: {
    fontSize: 24,
    fontFamily: 'Helvetica-Bold',
    color: '#1e40af',
  },
  statLabel: {
    fontSize: 10,
    color: '#64748b',
    marginTop: 4,
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  footer: {
    display: 'flex',
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
    marginTop: 40,
    paddingTop: 20,
    borderTop: '1pt solid #e2e8f0',
  },
  footerSection: {
    flex: 1,
  },
  footerText: {
    fontSize: 10,
    color: '#64748b',
    marginBottom: 2,
  },
  signature: {
    fontSize: 12,
    fontFamily: 'Helvetica-Bold',
    color: '#0f172a',
  },
  certificateId: {
    textAlign: 'right',
  },
  idLabel: {
    fontSize: 8,
    color: '#94a3b8',
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  idValue: {
    fontSize: 9,
    color: '#64748b',
    fontFamily: 'Courier',
    marginTop: 2,
  },
  logo: {
    textAlign: 'center',
    marginBottom: 15,
  },
  logoText: {
    fontSize: 28,
    fontFamily: 'Helvetica-Bold',
    color: '#1e40af',
  },
  logoSubtext: {
    fontSize: 10,
    color: '#64748b',
    marginTop: 2,
  },
});

interface CertificateTemplateProps {
  data: CertificateData;
}

export const CertificateTemplate: React.FC<CertificateTemplateProps> = ({ data }) => {
  return (
    <Document>
      <Page size="A4" orientation="landscape" style={styles.page}>
        <View style={styles.border}>
          <View style={styles.innerBorder}>
            {/* Header with Logo */}
            <View style={styles.header}>
              <View style={styles.logo}>
                <Text style={styles.logoText}>WorkWise</Text>
                <Text style={styles.logoSubtext}>Workday Expertise Platform</Text>
              </View>
              <Text style={styles.title}>Certificate of Achievement</Text>
            </View>

            {/* Main Content */}
            <View style={styles.content}>
              <Text style={styles.presentedTo}>Presented To</Text>
              <Text style={styles.userName}>{data.userName}</Text>

              <Text style={styles.achievement}>
                For successfully completing the
              </Text>
              <Text style={styles.milestoneName}>{data.milestoneName}</Text>
              <Text style={styles.milestoneDescription}>
                {data.milestoneDescription}
              </Text>

              {/* Statistics */}
              <View style={styles.stats}>
                <View style={styles.statBox}>
                  <Text style={styles.statValue}>{data.patternsCompleted}</Text>
                  <Text style={styles.statLabel}>Patterns Completed</Text>
                </View>
                <View style={styles.statBox}>
                  <Text style={styles.statValue}>{data.averageScore}%</Text>
                  <Text style={styles.statLabel}>Average Score</Text>
                </View>
              </View>

              <Text style={styles.achievement}>
                Demonstrating mastery of Workday best practices and expertise patterns
              </Text>
            </View>

            {/* Footer */}
            <View style={styles.footer}>
              <View style={styles.footerSection}>
                <Text style={styles.footerText}>Completion Date</Text>
                <Text style={styles.signature}>{data.completionDate}</Text>
              </View>

              <View style={[styles.footerSection, styles.certificateId]}>
                <Text style={styles.idLabel}>Certificate ID</Text>
                <Text style={styles.idValue}>{data.certificateId}</Text>
              </View>
            </View>
          </View>
        </View>
      </Page>
    </Document>
  );
};
