/**
 * Seed Test Customers for Demo
 * Run: npx ts-node -r tsconfig-paths/register scripts/seed-test-customers.ts
 */

import { NestFactory } from '@nestjs/core';
import { AppModule } from '../src/app.module';
import { Model } from 'mongoose';
import { getModelToken } from '@nestjs/mongoose';
import { generateId } from '../src/shared/utils';

const testCustomers = [
  {
    firstName: 'Олександр',
    lastName: 'Петренко',
    email: 'o.petrenko@gmail.com',
    phone: '+380501234567',
    type: 'individual',
    status: 'active',
    source: 'website',
    totalLeads: 3,
    totalDeals: 2,
    totalDeposits: 15000,
    totalRevenue: 45000,
    city: 'Київ',
    country: 'Україна',
  },
  {
    firstName: 'Марія',
    lastName: 'Коваленко',
    email: 'm.kovalenko@ukr.net',
    phone: '+380672345678',
    type: 'individual',
    status: 'vip',
    source: 'referral',
    totalLeads: 5,
    totalDeals: 4,
    totalDeposits: 35000,
    totalRevenue: 120000,
    city: 'Львів',
    country: 'Україна',
  },
  {
    firstName: 'Іван',
    lastName: 'Сидоренко',
    email: 'ivan.sydorenko@company.ua',
    phone: '+380633456789',
    type: 'company',
    company: 'АвтоЛюкс ТОВ',
    status: 'active',
    source: 'partner',
    totalLeads: 8,
    totalDeals: 6,
    totalDeposits: 75000,
    totalRevenue: 280000,
    city: 'Одеса',
    country: 'Україна',
  },
  {
    firstName: 'Наталія',
    lastName: 'Бондаренко',
    email: 'natalia.b@outlook.com',
    phone: '+380954567890',
    type: 'individual',
    status: 'active',
    source: 'social_media',
    totalLeads: 2,
    totalDeals: 1,
    totalDeposits: 8000,
    totalRevenue: 32000,
    city: 'Харків',
    country: 'Україна',
  },
  {
    firstName: 'Дмитро',
    lastName: 'Шевченко',
    email: 'd.shevchenko@gmail.com',
    phone: '+380505678901',
    type: 'individual',
    status: 'active',
    source: 'advertisement',
    totalLeads: 1,
    totalDeals: 1,
    totalDeposits: 5000,
    totalRevenue: 25000,
    city: 'Дніпро',
    country: 'Україна',
  },
];

async function seedTestCustomers() {
  console.log('🚗 Seeding Test Customers for BIBI Cars Demo...\n');

  try {
    const app = await NestFactory.createApplicationContext(AppModule, {
      logger: ['error', 'warn'],
    });

    const customerModel = app.get<Model<any>>(getModelToken('Customer'));

    let created = 0;
    let skipped = 0;

    for (const customer of testCustomers) {
      const existing = await customerModel.findOne({ email: customer.email });
      if (existing) {
        console.log(`⏭️  Skip: ${customer.email} (already exists)`);
        skipped++;
        continue;
      }

      await customerModel.create({
        id: generateId(),
        ...customer,
        lastInteractionAt: new Date(),
        isDeleted: false,
        createdBy: 'seed-script',
      });

      console.log(`✅ Created: ${customer.firstName} ${customer.lastName} (${customer.email})`);
      created++;
    }

    console.log(`\n📊 Results: ${created} created, ${skipped} skipped`);
    console.log('\n✅ Test customers seeded successfully!');

    await app.close();
    process.exit(0);
  } catch (error) {
    console.error('❌ Error seeding customers:', error.message);
    process.exit(1);
  }
}

seedTestCustomers();
