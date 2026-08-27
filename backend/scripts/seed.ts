/**
 * CLI Seed Script
 * Run: npx ts-node -r tsconfig-paths/register scripts/seed.ts
 * 
 * Options:
 *   --clear    Clear all data before seeding
 *   --leads    Include test leads
 */

import { NestFactory } from '@nestjs/core';
import { AppModule } from '../src/app.module';
import { SeedService } from '../src/bootstrap/seed.service';

async function runSeed() {
  console.log('🌱 CRM Database Seed Script');
  console.log('============================\n');
  
  const args = process.argv.slice(2);
  const shouldClear = args.includes('--clear');
  const includeLeads = args.includes('--leads');
  
  try {
    const app = await NestFactory.createApplicationContext(AppModule, {
      logger: ['error', 'warn'],
    });
    
    const seedService = app.get(SeedService);
    
    if (shouldClear) {
      console.log('⚠️  Clearing test data...');
      await seedService.clearTestData();
    }
    
    console.log('Running seed...\n');
    const result = await seedService.seedAll();
    
    if (includeLeads) {
      console.log('Adding test leads...');
      result.leads = await seedService.seedTestLeads(10);
    }
    
    console.log('\n✅ Seed Results:');
    console.log(`   Users: ${result.users}`);
    console.log(`   Leads: ${result.leads}`);
    console.log(`   Automation Rules: ${result.automationRules}`);
    console.log(`   Message Templates: ${result.messageTemplates}`);
    console.log(`   Settings: ${result.settings}`);
    
    await app.close();
    console.log('\n✅ Seed completed successfully!');
    process.exit(0);
    
  } catch (error) {
    console.error('\n❌ Seed failed:', error.message);
    process.exit(1);
  }
}

runSeed();
