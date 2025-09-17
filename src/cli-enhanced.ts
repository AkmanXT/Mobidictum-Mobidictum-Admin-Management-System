import { loadConfig } from './config';
import { logger } from './logger';
import { FientaClient } from './fienta';
import { FientaEnhancedScraper } from './fienta-enhanced';
import fs from 'fs';
import path from 'path';

// Enable debug logging if requested
if (process.argv.includes('--debug')) {
  logger.level = 'debug';
}

async function main(): Promise<void> {
  const config = loadConfig();
  const args = process.argv.slice(2);
  
  // Check if we're running enhanced scraping commands
  const command = args[0];
  
  if (command === 'scrape-usage') {
    // Scrape code usage data
    const eventId = args[1] || process.env.FIENTA_EVENT_ID;
    const includeOrders = args.includes('--with-orders');
    const outputPath = args.find(a => a.startsWith('--output='))?.split('=')[1] || 'code-usage-report.json';
    
    if (!eventId) {
      logger.error('Event ID required. Use: npm run dev -- scrape-usage <eventId> [--with-orders] [--output=file.json]');
      process.exit(1);
    }

    const client = new FientaClient(config);
    try {
      await client.start();
      await client.login();
      
      const page = client.requirePage();
      const scraper = new FientaEnhancedScraper(page, config.fientaBaseUrl);
      
      logger.info({ eventId, includeOrders }, 'Starting enhanced code usage scraping');
      
      const usageData = await scraper.getAllCodesWithUsage(eventId, includeOrders);
      
      // Save results
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      const finalPath = outputPath.includes('.') ? outputPath : `${outputPath}-${timestamp}.json`;
      
      fs.writeFileSync(finalPath, JSON.stringify(usageData, null, 2), 'utf8');
      logger.info({ path: finalPath, totalCodes: usageData.length }, 'Saved usage report');
      
      // Also create a CSV summary
      const csvPath = finalPath.replace('.json', '.csv');
      const csvHeader = 'Code,Orders Used,Order Limit,Tickets Used,Ticket Limit,Usage %,Status\n';
      const csvData = usageData.map(d => {
        const usagePercent = d.orderLimit > 0 ? Math.round((d.ordersUsed / d.orderLimit) * 100) : 0;
        const status = d.ordersUsed >= d.orderLimit ? 'FULL' : d.ordersUsed > 0 ? 'PARTIAL' : 'UNUSED';
        return `${d.code},${d.ordersUsed},${d.orderLimit},${d.ticketsUsed},${d.ticketLimit},${usagePercent}%,${status}`;
      }).join('\n');
      
      fs.writeFileSync(csvPath, csvHeader + csvData, 'utf8');
      logger.info({ path: csvPath }, 'Saved CSV summary');
      
    } finally {
      await client.stop();
    }
    return;
  }

  if (command === 'list-codes') {
    // Lightweight: just list which codes exist (for fast checking)
    const eventId = args[1] || process.env.FIENTA_EVENT_ID;
    const outputPath = args.find(a => a.startsWith('--output='))?.split('=')[1] || 'codes-list.json';
    
    if (!eventId) {
      logger.error('Event ID required. Use: npm run dev -- list-codes <eventId> [--output=file.json]');
      process.exit(1);
    }

    const client = new FientaClient(config);
    try {
      await client.start();
      await client.login();
      
      const page = client.requirePage();
      const scraper = new FientaEnhancedScraper(page, config.fientaBaseUrl);
      
      logger.info({ eventId }, 'Starting smart code existence check');
      
      const result = await scraper.getCodesList(eventId);
      
      // Save results with both codes and metadata
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      const finalPath = outputPath.includes('.') ? outputPath : `${outputPath}-${timestamp}.json`;
      
      const outputData = {
        codes: result.codes,
        metadata: result.metadata,
        timestamp: new Date().toISOString(),
        eventId: eventId,
        stats: {
          totalCodes: result.codes.length,
          metadataCaptured: Object.keys(result.metadata).length,
          metadataPercentage: Math.round((Object.keys(result.metadata).length / result.codes.length) * 100)
        }
      };
      
      fs.writeFileSync(finalPath, JSON.stringify(outputData, null, 2), 'utf8');
      logger.info({ 
        path: finalPath, 
        totalCodes: result.codes.length,
        metadataCaptured: Object.keys(result.metadata).length 
      }, 'Saved smart codes list');
      
    } finally {
      await client.stop();
    }
    return;
  }
  
  if (command === 'scrape-code-details') {
    // Scrape detailed info for specific codes
    const eventId = args[1] || process.env.FIENTA_EVENT_ID;
    const codes = args.slice(2).filter(a => !a.startsWith('--'));
    const outputPath = args.find(a => a.startsWith('--output='))?.split('=')[1] || 'code-details.json';
    
    if (!eventId || codes.length === 0) {
      logger.error('Usage: npm run dev -- scrape-code-details <eventId> <code1> [code2...] [--output=file.json]');
      process.exit(1);
    }

    const client = new FientaClient(config);
    try {
      await client.start();
      await client.login();
      
      const page = client.requirePage();
      const scraper = new FientaEnhancedScraper(page, config.fientaBaseUrl);
      
      const results = [];
      for (const code of codes) {
        logger.info({ code }, 'Scraping code details');
        const details = await scraper.getCodeDetails(eventId, code);
        if (details) {
          results.push(details);
        }
      }
      
      fs.writeFileSync(outputPath, JSON.stringify(results, null, 2), 'utf8');
      logger.info({ path: outputPath, count: results.length }, 'Saved code details');
      
    } finally {
      await client.stop();
    }
    return;
  }
  
  if (command === 'export-buyers') {
    // Export all buyers who used codes
    const eventId = args[1] || process.env.FIENTA_EVENT_ID;
    const outputPath = args.find(a => a.startsWith('--output='))?.split('=')[1] || 'buyers-export.csv';
    
    if (!eventId) {
      logger.error('Event ID required. Use: npm run dev -- export-buyers <eventId> [--output=file.csv]');
      process.exit(1);
    }

    const client = new FientaClient(config);
    try {
      await client.start();
      await client.login();
      
      const page = client.requirePage();
      const scraper = new FientaEnhancedScraper(page, config.fientaBaseUrl);
      
      logger.info({ eventId }, 'Exporting buyer information');
      
      const usageData = await scraper.getAllCodesWithUsage(eventId, true);
      
       // Create buyer-centric CSV
       const csvHeader = 'Order ID,Date,Email,Name,Phone,Code Used,Tickets,Total,Status,Ticket Types\n';
       const csvRows: string[] = [];
       
       for (const codeData of usageData) {
         for (const order of codeData.orders) {
           const ticketTypes = [...new Set(order.ticketDetails.map(t => t.ticketType).filter(t => t))].join(';');
           const ticketTypesDisplay = ticketTypes || 'Unknown';
           csvRows.push([
             order.orderId,
             order.orderDate,
             `"${order.customerEmail}"`, // Quote email to handle commas
             `"${order.customerName || ''}"`, // Quote name to handle commas
             order.customerPhone || '',
             order.discountCode || '',
             order.ticketCount,
             `"${order.totalAmount} ${order.currency}"`, // Quote price to handle commas
             order.status,
             `"${ticketTypesDisplay}"` // Quote ticket types to handle semicolons
           ].join(','));
         }
       }
      
      fs.writeFileSync(outputPath, csvHeader + csvRows.join('\n'), 'utf8');
      logger.info({ path: outputPath, totalOrders: csvRows.length }, 'Saved buyer export');
      
    } finally {
      await client.stop();
    }
    return;
  }
  
  // Show help if no recognized command
  if (command && !['--help', '-h'].includes(command)) {
    logger.warn({ command }, 'Unknown command');
  }
  
  console.log(`
Fienta Enhanced CLI - Additional Commands:

USAGE DATA SCRAPING:
  npm run dev -- scrape-usage <eventId> [--with-orders] [--output=report.json]
    Scrape all codes with usage statistics
    --with-orders: Include detailed order/buyer information

  npm run dev -- list-codes <eventId> [--output=codes.json]
    Smart & fast: Get codes list + capture essential metadata (IDs, edit URLs)

CODE DETAILS:
  npm run dev -- scrape-code-details <eventId> <code1> [code2...] [--output=details.json]
    Get detailed information about specific codes

BUYER EXPORT:
  npm run dev -- export-buyers <eventId> [--output=buyers.csv]
    Export all buyers who used discount codes

EXAMPLES:
  npm run dev -- list-codes 118714
  npm run dev -- scrape-usage 118714
  npm run dev -- scrape-usage 118714 --with-orders --output=full-report.json
  npm run dev -- scrape-code-details 118714 VOODOO-02-1SX FLEXIONMOBILE-01-QW7
  npm run dev -- export-buyers 118714 --output=event-buyers.csv

For original commands, run without arguments or see README.
  `);
}

main().catch((err) => {
  logger.error({ err }, 'Fatal error');
  process.exit(1);
});
